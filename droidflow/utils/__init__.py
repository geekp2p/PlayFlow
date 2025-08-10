"""Utility package exposing core helpers and screenshot streaming."""

import os as _os

# re-export DEVICE_SERIAL (legacy shim; live env)
DEVICE_SERIAL = _os.getenv("DEVICE_SERIAL")

# Core helpers
from .core import *  # noqa: F401,F403

# Video streaming (H.264 / minicap)
from .videostream import streamer as _vs, video_frame, video_stream

# PNG fallback
from .screenshot import ScreenshotStreamer

_ss = ScreenshotStreamer()


def screenshot_b64():
    """Return the latest device screenshot encoded as base64."""
    return _ss.screenshot_b64()

from .core import log as _log


def screenshot_stream():
    # บังคับไม่ใช้ scrcpy/minicap, ใช้การจับภาพแบบเดิมเสมอ
    _log("VideoStreamer: forced screenshot fallback")
    return _ss.screenshot_stream()

# def screenshot_stream():
#     try:
#         return video_stream()        # ⚡️ใช้ VideoStreamer เป็นหลัก
#     except Exception:
#         return _ss.screenshot_stream()