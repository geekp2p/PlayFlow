#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-performance screen streamer

ลำดับความพยายาม
1. scrcpy-server.jar (H.264 over socket)            ⚡  <0.1 s latency
2. minicap (JPEG frames over socket)                ⚡  ~0.1 s
3. Screenshot fallback (PNG → JPEG)                 🐢  0.2-0.4 s

หากอุปกรณ์ยังไม่มีไฟล์ server จะ push ให้ครั้งแรกแบบอัตโนมัติ
"""

import os
import subprocess
import threading
import socket
import struct
import time
import atexit
from io import BytesIO

import av

from .screenshot import ScreenshotStreamer
from .core import log as _log

# ───────────── config ─────────────
DEVICE_SERIAL = os.getenv("DEVICE_SERIAL")
ADB_PATH      = os.getenv("ADB_PATH", "adb")
FPS           = int(os.getenv("FPS", "30"))
BITRATE       = os.getenv("BITRATE_M", "4M")
SCRCPY_VER    = os.getenv("SCRCPY_SERVER_VER", "1.25")   # เวอร์ชันที่ใช้รันบน device

# เส้นทางที่ “น่าจะ” มี scrcpy-server.jar ในเครื่อง host
_LOCAL_CANDIDATES = [
    os.getenv("SCRCPY_SERVER_JAR", ""),                       # ระบุผ่าน env ได้
    r"C:\\Program Files\\Scrcpy\\scrcpy-server.jar",             # Windows (choco)
    "/usr/local/share/scrcpy/scrcpy-server.jar",              # macOS / Linux
    "/usr/share/scrcpy/scrcpy-server.jar",
]

# ชื่อไฟล์บนอุปกรณ์
_DEVICE_JAR_PATH = "/data/local/tmp/scrcpy-server.jar"


class VideoStreamer:
    """scrcpy / minicap-based streaming with automatic fallback."""

    _proc = None
    _sock = None
    _lock = threading.Lock()
    _last_jpeg: bytes = b""

    def __init__(self) -> None:
        self._fallback = ScreenshotStreamer()
        atexit.register(self._cleanup)

    # ───────────── adb helper ─────────────
    def _adb(self, *args: str) -> list[str]:
        cmd = [ADB_PATH]
        if DEVICE_SERIAL:
            cmd += ["-s", DEVICE_SERIAL]
        return cmd + list(args)

    # ───────────── scrcpy helpers ─────────────
    def _ensure_scrcpy_server(self) -> bool:
        """
        ถ้า `scrcpy-server.jar` ยังไม่มีในอุปกรณ์ → พยายาม push จาก host
        Returns True เมื่อไฟล์พร้อมใช้งานบน device
        """
        # 1) device already has it?
        try:
            subprocess.check_call(
                self._adb("shell", "test", "-f", _DEVICE_JAR_PATH),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except subprocess.CalledProcessError:
            pass  # ไม่มีไฟล์ → ดำเนินต่อด้านล่าง

        # 2) หาไฟล์บน host ตาม path ที่เตรียมไว้
        for cand in _LOCAL_CANDIDATES:
            if cand and os.path.isfile(cand):
                try:
                    subprocess.check_call(
                        self._adb("push", cand, _DEVICE_JAR_PATH),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return True
                except Exception:
                    pass

        # 3) ดึงจาก package `scrcpy` ที่ติดตั้งผ่าน pip
        try:
            import inspect, scrcpy  # type: ignore
            jar = os.path.join(os.path.dirname(inspect.getfile(scrcpy)),
                               "scrcpy-server.jar")
            if os.path.isfile(jar):
                subprocess.check_call(
                    self._adb("push", jar, _DEVICE_JAR_PATH),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
        except Exception:
            pass

        # 4) ยอมแพ้
        return False

    def _start_scrcpy(self) -> bool:
        """พยายามเปิด scrcpy server แล้วตั้ง socket รับสตรีม H.264"""
        if not self._ensure_scrcpy_server():
            return False

        try:
            # forward พอร์ตก่อน (ปลอดภัยแม้ซ้ำซ้อน)
            subprocess.run(
                self._adb("forward", "tcp:27183", "localabstract:scrcpy"),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            self._proc = subprocess.Popen(
                self._adb(
                    "shell",
                    f"CLASSPATH={_DEVICE_JAR_PATH}",
                    "app_process", "/",
                    "com.genymobile.scrcpy.Server",
                    SCRCPY_VER,
                    "log_level=W",
                    f"bit_rate={BITRATE}",
                    f"max_fps={FPS}",
                    "control=false",
                    "video=true",
                    "send_frame_meta=false",
                ),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )

            self._sock = socket.create_connection(("127.0.0.1", 27183), timeout=5)
            threading.Thread(target=self._reader_h264, daemon=True).start()
            return True
        except Exception:
            self._cleanup()
            return False

    # ───────────── minicap helpers ─────────────
    def _start_minicap(self) -> bool:
        """
        พยายามเปิด minicap (ต้องมี binary + .so บนอุปกรณ์แล้ว)
        ไม่ทำ auto-push ในรุ่นนี้ — สามารถเติมได้ภายหลัง
        """
        try:
            out = subprocess.check_output(
                self._adb("shell", "wm", "size"),
                stderr=subprocess.DEVNULL
            ).decode(errors="ignore")
            w, h = out.strip().split()[-1].split("x")

            cmd = [
                "shell",
                "LD_LIBRARY_PATH=/data/local/tmp",
                "/data/local/tmp/minicap",
                "-P", f"{w}x{h}@{w}x{h}/0",
                "-S",
            ]
            self._proc = subprocess.Popen(
                self._adb(*cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0
            )
            subprocess.check_call(
                self._adb("forward", "tcp:1717", "localabstract:minicap"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self._sock = socket.create_connection(("127.0.0.1", 1717), timeout=5)
            threading.Thread(target=self._reader_minicap, daemon=True).start()
            return True
        except Exception:
            self._cleanup()
            return False

    # ───────────── generic helpers ─────────────
    def _cleanup(self) -> None:
        """หยุดโปรเซส & ปิด socket"""
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._sock = None
        self._proc = None

    def _ensure_server(self) -> bool:
        # server ยังรันอยู่
        if self._proc and self._proc.poll() is None:
            return True

        self._cleanup()
        # 1) scrcpy
        if self._start_scrcpy():
            _log("VideoStreamer: using scrcpy")
            return True
        # 2) minicap
        if self._start_minicap():
            _log("VideoStreamer: using minicap")
            return True

        _log("VideoStreamer: fallback to screencap")
        return False


    # ───────────── stream readers ─────────────
    def _reader_h264(self):
        """ถอดรหัส H.264 → JPEG เก็บเฟรมล่าสุด"""
        try:
            container = av.open(self._sock.makefile('rb'), format='h264')
            for frame in container.decode(video=0):
                buf = BytesIO()
                frame.to_image().save(buf, format='JPEG', quality=40)
                with self._lock:
                    self._last_jpeg = buf.getvalue()
        except Exception:
            self._cleanup()

    def _reader_minicap(self):
        """อ่าน stream minicap (JPEG raw)"""
        s = self._sock
        try:
            s.recv(24)  # banner
            while True:
                size = struct.unpack('<I', s.recv(4))[0]
                data = b''
                while len(data) < size:
                    chunk = s.recv(size - len(data))
                    if not chunk:
                        return
                    data += chunk
                with self._lock:
                    self._last_jpeg = data
        except Exception:
            self._cleanup()

    # ───────────── public API ─────────────
    def jpeg(self) -> bytes:
        """
        คืนค่าภาพล่าสุด (JPEG) – พยายามใช้ video backend,
        ถ้าไม่ได้ให้ fallback เป็น screenshot
        """
        if self._ensure_server():
            with self._lock:
                if self._last_jpeg:
                    return self._last_jpeg
        # final fallback
        return self._fallback._grab_screenshot()

    def mjpeg(self):
        tpl = (b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: %d\r\n\r\n")
        while True:
            jpg = self.jpeg()
            yield tpl % len(jpg) + jpg + b"\r\n"
            time.sleep(1 / max(FPS, 1))



# ───────────── module-level helpers ─────────────
streamer = VideoStreamer()

def video_frame() -> bytes:
    """ดึงเฟรมเดี่ยว (JPEG)"""
    return streamer.jpeg()

def video_stream():
    """สตรีม MJPEG ต่อเนื่อง"""
    return streamer.mjpeg()