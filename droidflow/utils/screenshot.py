import io
import os
import re
import threading
import time
import subprocess
import base64
from typing import Optional

from PIL import Image
import uiautomator2 as u2

# ───────────── config ─────────────
DEVICE_SERIAL  = os.getenv("DEVICE_SERIAL")
ADB_PATH       = os.getenv("ADB_PATH", "adb")
_SS_INTERVAL   = float(os.getenv("SS_INTERVAL", "0.02"))   # seconds between captures
# _SS_INTERVAL   = 0.08      # ดึงภาพทุก 0.08 s (≈12 fps) — ไม่อ่าน env แล้ว
_ENV_W         = os.getenv("SS_WIDTH")                       # raw env value (None / "auto" / int)
_JPEG_Q        = int(os.getenv("SS_QUALITY", "70"))         # JPEG quality (0‑100)


# ────────────────── helpers ──────────────────

def _adb_cmd(extra: list[str]) -> list[str]:
    cmd = [ADB_PATH]
    if DEVICE_SERIAL:
        cmd += ["-s", DEVICE_SERIAL]
    return cmd + extra


def _detect_screen_width() -> int:
    """Best‑effort detect physical screen width in *pixels*.
    1) `adb shell wm size`  ➜  "Physical size: 1080x2340"
    2) `uiautomator2`       ➜  d.window_size()  → (w, h)
    Returns 0 if detection fails (caller decides fallback)."""
    # —— ADB path ——
    try:
        out = subprocess.check_output(_adb_cmd(["shell", "wm", "size"]), timeout=2, text=True, errors="ignore")
        m = re.search(r"Physical size:\s*(\d+)x(\d+)", out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    # —— uiautomator2 path ——
    try:
        d = u2.connect_usb(DEVICE_SERIAL) if DEVICE_SERIAL else u2.connect()
        w, _ = d.window_size()
        return int(w)
    except Exception:
        pass
    return 0


# ─── dynamic width logic ───
_DETECTED_W = _detect_screen_width()

# force FULL width by default
_TARGET_W = min(_DETECTED_W or 720, 1280)

if _ENV_W and _ENV_W.isdigit():               # ยังกำหนด SS_WIDTH=360 ได้ตามเดิม
    _TARGET_W = int(_ENV_W)
elif _ENV_W and _ENV_W.lower() == "auto":     # หรือ SS_WIDTH=auto ก็ full width
    _TARGET_W = min(_DETECTED_W or 720, 1280)



class ScreenshotStreamer:
    """Capture device screenshots in a background thread and stream them as down‑scaled JPEGs.

    Improvements over the original version:
      •  Auto‑detect device resolution the first time the module is imported.  No need to
         set SS_WIDTH manually.  You can still force a width via env: `SS_WIDTH=360` or
         request full res with `SS_WIDTH=auto`.
      •  Keeps the same down‑scale/JPEG pipeline that reduces latency & bandwidth dramatically.
    """

    def __init__(self):
        self._last_jpeg: Optional[bytes] = None   # already processed JPEG
        self._thread_started = False
        self._lock = threading.Lock()

    # ───────────── private helpers ─────────────
    def _grab_png(self) -> bytes:
        """Capture a *raw PNG* screenshot via `adb exec-out screencap` with uiautomator2 fallback."""
        try:
            cmd = _adb_cmd(["exec-out", "screencap", "-p"])
            return subprocess.check_output(cmd, timeout=2)
        except Exception:
            buf = io.BytesIO()
            try:
                d = u2.connect_usb(DEVICE_SERIAL) if DEVICE_SERIAL else u2.connect()
            except Exception:
                d = u2.connect(f"adb://{DEVICE_SERIAL}")
            d.screenshot().save(buf, format="PNG")
            return buf.getvalue()

    def _process(self, png_bytes: bytes) -> bytes:
        """Down‑scale & transcode PNG → JPEG bytes using the global `_TARGET_W`."""
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        w, h = img.size
        if _TARGET_W and w > _TARGET_W:
            ratio = _TARGET_W / w
            img = img.resize((int(w * ratio), int(h * ratio)), Image.BILINEAR)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=_JPEG_Q, optimize=True)
        return out.getvalue()

        # backward‑compat shim for old videostream.py
    def _grab_screenshot(self):
        """Return *raw PNG* bytes (legacy name expected by videostream)."""
        return self._grab_png()

    # ───────────── worker thread ─────────────
    def _screenshot_loop(self):
        while True:
            try:
                jpg = self._process(self._grab_png())
                with self._lock:
                    self._last_jpeg = jpg
            except Exception:
                pass
            time.sleep(_SS_INTERVAL)

    def _ensure_thread(self):
        if not self._thread_started:
            threading.Thread(target=self._screenshot_loop, daemon=True).start()
            self._thread_started = True

    # ───────────── public API ─────────────
    def screenshot_b64(self) -> str:
        """Return latest screen as Base64‑encoded JPEG."""
        self._ensure_thread()
        with self._lock:
            img = self._last_jpeg or self._process(self._grab_png())
        return base64.b64encode(img).decode()
    
    def screenshot_stream(self):
        """Yield an MJPEG stream with Content-Length per frame for throughput calculation."""
        self._ensure_thread()
        boundary_tpl = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n"
        while True:
            with self._lock:
                img = self._last_jpeg or self._process(self._grab_png())
            yield boundary_tpl % len(img) + img + b"\r\n"           
            time.sleep(_SS_INTERVAL)
    
    # def screenshot_stream(self):
    #     """Yield an MJPEG stream with Content-Length per frame for throughput calculation."""
    #     self._ensure_thread()
    #     # ใส่ %d ไว้ใน header เพื่อแทนขนาดของ JPEG แต่ละเฟรม
    #     boundary = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n"
    #     while True:
    #         with self._lock:
    #             img = self._last_jpeg or self._process(self._grab_png())
    #         # แทรกความยาวของ img ลงไปใน header
    #         yield boundary % len(img) + img + b"\r\n"
    #         time.sleep(_SS_INTERVAL)

    # def screenshot_stream(self):
    #     """Yield an MJPEG stream (multipart/x‑mixed‑replace)."""
    #     self._ensure_thread()
    #     boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
    #     while True:
    #         with self._lock:
    #             img = self._last_jpeg or self._process(self._grab_png())
    #         yield boundary + img + b"\r\n"
    #         time.sleep(_SS_INTERVAL)