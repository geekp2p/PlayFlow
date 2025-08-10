#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import threading
import re
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler

import os
import utils
from utils import connect
from utils.core import _adb_cmd
import runner

# Try an initial connect but don't crash if device not ready yet.
try:
    _d = utils.connect()
    print("Device:", getattr(_d, "serial", "?"))
    try:
        print("Window:", _d.window_size())
    except Exception:
        print("Window: ?")
except Exception as e:
    print("WARN engine: initial device connect failed:", e)

# ────────────────── config ──────────────────
DEVICE_SERIAL = utils.DEVICE_SERIAL
FLOW_DIR      = utils.FLOW_DIR
os.makedirs(FLOW_DIR, exist_ok=True)

# utils.DEVICE_SERIAL อาจไม่มี (หลัง refactor core.py)
# ใช้ env เป็นหลัก; ถ้าอยากดูค่า live ให้เรียก utils.core._current_device_serial() ถ้ามี
if hasattr(utils, "_current_device_serial"):
    DEVICE_SERIAL = utils._current_device_serial()
else:
    DEVICE_SERIAL = os.getenv("DEVICE_SERIAL")  # อาจ None

# FLOW_DIR ยังมีใน core.py (และ re-export) แต่กันพังไว้
FLOW_DIR = getattr(utils, "FLOW_DIR", "./flows")
os.makedirs(FLOW_DIR, exist_ok=True)

# ───────── scheduler ─────────
sched = BackgroundScheduler(timezone="UTC")
sched.start()

# ──────── expose runtime state ────────
actions   = utils.actions
prog_log  = utils.prog_log
sched_log = utils.sched_log

# ──────── core APIs ────────

# def screenshot_b64() -> str:
#     return utils.screenshot_b64()
def screenshot_stream():
    return utils.screenshot_stream()

def screenshot_b64() -> str:
    return utils.screenshot_b64()

def get_elements() -> list[dict]:
    return utils.get_elements()


def start_record():
    utils.start_record()


def stop_record():
    utils.stop_record()


def clear_actions():
    utils.clear_actions()


def record_click(args):
    utils.record_click(args)


def record_key(args):
    utils.record_key(args)


def record_type(args):
    utils.record_type(args)


def record_block(args):
    utils.record_block(args)


def inspect_element(args) -> dict:
    return utils.inspect_element(args)


def save_flow(payload):
    utils.save_flow(payload)


def load_flow(name) -> dict:
    return utils.load_flow(name)


def get_transactions() -> list[dict]:
    """
    Returns a list of all transaction rows, each with:
      { name: str, time: str, amount: str, bounds: str }
    """
    return utils.get_transactions()

def get_payment_info() -> dict:
    """
    Wrapper to read on-screen payment info.
    """
    return utils.read_payment_info()

# ──────── scheduler helpers ────────

def schedule_job(name: str, cron: str):
    """
    Schedule a saved flow by cron expression (min hour dom mon dow).
    """
    if not (name and cron):
        return
    # remove existing job
    if sched.get_job(name):
        sched.remove_job(name)

    m, h, dom, mo, dow = (cron.split() + ["*"]*5)[:5]
    sched.add_job(
        run_saved,
        "cron",
        id=name,
        minute=m,
        hour=h,
        day=dom,
        month=mo,
        day_of_week=dow,
        args=[name, "hybrid"]
    )
    utils.log(f"add job {name} {cron}", dest="sched")


def run_saved(name: str, mode: str):
    """
    Load a saved flow and run it in a background thread.
    """
    try:
        result = load_flow(name)
        if not result.get("ok"):
            raise FileNotFoundError(name)
        acts = result["actions"]
    except Exception as e:
        utils.log(f"load {name} fail {e}", dest="sched")
        return

    utils.log(f"job {name} start", dest="sched")
    threading.Thread(
        target=runner.run_flow,
        args=(acts, mode),
        daemon=True
    ).start()

# ──────── run-now / compile+run ────────

def run_now(mode: str = "hybrid"):
    """
    Run the current recorded actions immediately.
    """
    runner.run_now(mode)


def run_compile(acts_list, mode: str = "hybrid"):
    """
    Run a provided list of actions (e.g. compiled flow).
    """
    runner.run_compile(acts_list, mode)

# ──────── core APIs ────────

def record_swipe(args):
    utils.record_swipe(args)

# proxies ใหม่
def current_app() -> dict:
    return utils.current_app()

def open_app(pkg: str) -> tuple[bool, str]:
    return utils.open_app(pkg)


def close_app(pkg: str) -> tuple[bool, str]:
    return utils.close_app(pkg)


def get_main_activity(pkg: str) -> tuple[bool, str]:
    return utils.get_main_activity(pkg)


def restart_app(pkg: str, mode: str = "safe") -> tuple[bool, str]:
    return utils.restart_app(pkg, mode)

# ──────── click_by_selector ────────

def click_by_selector(sel: dict) -> bool:
    import utils, re, subprocess
    d = connect()
    utils.log(f"🔍 click_by_selector sel={sel}")
    # prepare selector args...
    args = {}
    if sel.get("rid"):  args["resourceId"] = sel["rid"]
    if sel.get("text"): args["text"]       = sel["text"]
    if sel.get("desc"): args["description"]= sel["desc"]

    try:
        el = d(**args)
        utils.log(f"   element.exists={el.exists}")
        if not el.exists:
            return False

        info_bounds = el.info.get("bounds", "")
        # ถ้าเป็น dict ให้อ่านค่าจาก key 'left','top','right','bottom'
        if isinstance(info_bounds, dict):
            l = info_bounds.get("left",0)
            t = info_bounds.get("top",0)
            r = info_bounds.get("right",0)
            btm = info_bounds.get("bottom",0)
        else:
            # เก่ายังรองรับ string
            nums = re.findall(r"\d+", info_bounds)
            if len(nums) != 4:
                el.click()
                return True
            l, t, r, btm = map(int, nums)

        cx, cy = (l + r)//2, (t + btm)//2
        utils.log(f"   tapping at ({cx},{cy})")
        subprocess.run(
          _adb_cmd(["shell", "input", "tap", str(cx), str(cy)]),
          check=False
        )
        return True

    except Exception as e:
        utils.log(f"   exception in click_by_selector: {e}")
        return False

def inspect_element_raw(args) -> dict:
    return utils.inspect_element_raw(args)


# def click_by_selector(sel: dict) -> bool:
#     d = connect()
#     # แปลงชื่อ key ให้ตรงกับ uiautomator2
#     args = {}
#     if sel.get("rid"):  args["resourceId"] = sel["rid"]
#     if sel.get("text"): args["text"]       = sel["text"]
#     if sel.get("desc"): args["description"]= sel["desc"]
#     try:
#         elem = getattr(d, "xpath" if False else "resourceId")
#         # อันนี้ตัวอย่างสำหรับ resourceId; หรือใช้ kwargs d(**args)
#         el = d(**args)
#         if el.exists:
#             el.click()
#             return True
#     except:
#         pass
#     return False