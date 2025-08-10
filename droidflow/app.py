#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os  # must import os before checking os.name
import sys
import shutil
import subprocess
import threading

# eventlet is used for async support. It tends to behave poorly on Windows, so
# only enable it on non-Windows platforms. If anything goes wrong while
# importing or patching eventlet we gracefully fall back to Flask-SocketIO's
# default threading mode.
if os.name != 'nt':
    try:
        import eventlet
        # Patch standard library to cooperate with eventlet (monkey-patch before
        # other imports)
        eventlet.monkey_patch()
        _async_mode = 'eventlet'
    except Exception:
        eventlet = None
        _async_mode = 'threading'
else:
    eventlet = None
    _async_mode = 'threading'

from flask import Flask, render_template, jsonify, request, Response
from flask_socketio import SocketIO, emit  # emit ใช้ push state
import engine
from utils.core import _adb_cmd  # เพื่อ honor ADB_PATH และ DEVICE_SERIAL

import json

# --- dynamic app list from env -------------------------------------------------
_APP_LIST_JSON = os.getenv("DROIDFLOW_APPS", "[]")
try:
    APP_LIST = json.loads(_APP_LIST_JSON)
    if not isinstance(APP_LIST, list):
        APP_LIST = []
    else:
        _norm = []
        for ent in APP_LIST:
            if not isinstance(ent, dict):
                continue
            label = str(ent.get("label") or ent.get("name") or "?")
            pkg   = str(ent.get("pkg") or ent.get("package") or "")
            if pkg:
                _norm.append({"label": label, "pkg": pkg})
        APP_LIST = _norm
except Exception:  # noqa: BLE001
    APP_LIST = []

INSTANCE_NAME = os.getenv("INSTANCE_NAME", "")

# ตรวจสอบว่ามี pty (Unix-only) หรือไม่
try:
    import pty
    has_pty = True
except ImportError:
    has_pty = False  # Windows ไม่มี module pty

app = Flask(__name__, template_folder="templates")

# Use the async mode determined above and allow CORS from any origin
socketio = SocketIO(app, async_mode=_async_mode,
                    cors_allowed_origins="*")

# ---------- helper : push incremental state ----------
def push_state(delta: dict):
    """Emit only the changed pieces to every connected client."""
    if delta:
        socketio.emit("state_delta", delta, namespace="/ui")

# ---------- monkey-patch utils.log ----------
import utils
_orig_log = utils.log

def _broadcasting_log(msg, dest="prog"):
    _orig_log(msg, dest)                # เขียนไฟล์เหมือนเดิม
    push_state({f"{dest}_append": msg}) # แล้ว push ให้ client

utils.log = _broadcasting_log

app.sched = engine.sched   # expose scheduler
term_fd = None

# —— Transactions helper ——
@app.route("/transactions")
def transactions():
    """
    Returns a list of all transaction rows:
      [{ name: str, time: str, amount: str, bounds: str }, …]
    """
    return jsonify(engine.get_transactions())

# —— Stream ——
@app.route("/stream")
def stream():
    return Response(
        engine.screenshot_stream(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

# —— Home & state ——
@app.route("/")
def home():
    return render_template("index.html", app_list=APP_LIST, instance_name=INSTANCE_NAME)


@app.route("/devices")
def list_devices_route():
    """Return list of ADB-visible serial strings (state=device)."""
    import re
    adb_path = os.getenv("ADB_PATH", "adb")
    host = port = None
    adb_sock = os.getenv("ADB_SERVER_SOCKET")
    cmd = [adb_path]
    if adb_sock and adb_sock.startswith("tcp:"):
        hostport = adb_sock[4:]
        if ':' in hostport:
            host, port = hostport.split(':', 1)
        if host:
            cmd += ["-H", host]
        if port:
            cmd += ["-P", port]
    cmd += ["devices"]
    try:
        out = subprocess.check_output(cmd, text=True, errors="ignore")
    except Exception:  # noqa: BLE001
        return jsonify([])
    devs = []
    for line in out.splitlines()[1:]:
        m = re.match(r"^(\S+)\s+device$", line.strip())
        if m:
            devs.append(m.group(1))
    return jsonify(devs)

@app.route("/terminal")
def terminal_page():
    return render_template("terminal.html")

@app.route("/state")
def state():
    """Deprecated: kept for backward compatibility."""
    return "", 204

# —— Foreground app ——
@app.route("/current_app")
def current_app_route():
    return jsonify(engine.current_app())

@app.route("/record_swipe")
def record_swipe():
    engine.record_swipe(request.args)
    return "", 204

# —— Package info ——
@app.route("/pkg_info")
def pkg_info():
    pkg = request.args.get("pkg", "")
    ok, act = engine.get_main_activity(pkg)
    return jsonify({"ok": ok, "activity": act})

# —— App control ——
@app.route("/open")
def open_app_route():
    ok, msg = engine.open_app(request.args.get("pkg", ""))
    return jsonify({"ok": ok, "msg": msg})

@app.route("/close")
def close_app_route():
    ok, msg = engine.close_app(request.args.get("pkg", ""))
    return jsonify({"ok": ok, "msg": msg})

@app.route("/restart")
def restart_route():
    pkg = request.args.get("pkg", "")
    mode = request.args.get("mode", "safe")
    ok, msg = engine.restart_app(pkg, mode)
    return jsonify({"ok": ok, "msg": msg})

# —— UI helpers ——
@app.route("/elements")
def elements():
    return jsonify(engine.get_elements())

# —— Recording control ——
@app.route("/start_record")
def start_record():
    engine.start_record()
    return "", 204

@app.route("/stop_record")
def stop_record():
    engine.stop_record()
    return "", 204

@app.route("/clear_actions")
@app.route("/clear_actions")
def clear_actions():
    engine.clear_actions()
    return "", 204

# —— Record individual actions ——
@app.route("/record_click")
def record_click():
    engine.record_click(request.args)
    return "", 204

@app.route("/record_key")
def record_key():
    engine.record_key(request.args)
    return "", 204

@app.route("/record_type")
def record_type():
    engine.record_type(request.args)
    return "", 204

@app.route("/record_block")
def record_block():
    engine.record_block(request.args)
    return "", 204

# —— Inspect element under cursor ——
@app.route("/inspect")
def inspect_element():
    info = engine.inspect_element(request.args)
    return jsonify(info)

# # —— Inspect element แบบ raw (ไม่กรอง clickable) ——
# @app.route("/inspect_raw")
# def inspect_element_raw():
#     # เรียก inspect_element เวอร์ชันใหม่ที่ fallback ครอบทุก node
#     info = engine.inspect_element(request.args)
#     return jsonify(info)

# —— Inspect element แบบ raw (ไม่กรอง clickable) ——
@app.route("/inspect_raw")
def inspect_element_raw():
    info = engine.inspect_element_raw(request.args)
    return jsonify(info)

# —— Save & load flows ——
@app.route("/save", methods=["POST"])
def save_flow():
    payload = request.get_json(force=True)
    engine.save_flow(payload)
    return "", 204

@app.route("/load")
def load_flow():
    name = request.args.get("name", "")
    result = engine.load_flow(name)
    return jsonify(result)

# —— Scheduling ——
@app.route("/schedule")
def schedule():
    name = request.args.get("name", "")
    cron = request.args.get("cron", "")
    engine.schedule_job(name, cron)
    return "", 204

# —— Run now & compile+run ——
@app.route("/run")
def run_now():
    mode = request.args.get("mode", "hybrid")
    engine.run_now(mode)
    return "", 204

@app.route("/run_compile", methods=["POST"])
def run_compile():
    # รอ implement runner.run_compile
    return "", 204

@app.route("/click_element", methods=["GET"])
def click_element():
    # รับ rid/text/desc มาเป็น query params
    sel = {}
    for k in ("rid","text","desc"):
        v = request.args.get(k)
        if v:
            sel[k] = v
    # เรียก engine ให้คลิก selector นั้น
    ok = engine.click_by_selector(sel)
    return jsonify({"ok": ok})

# —— Terminal I/O ——
if has_pty:
    @socketio.on('connect', namespace='/term')
    def term_connect():
        global term_fd
        pid, term_fd = pty.fork()
        if pid == 0:
            os.execvp('adb', ['adb', 'shell'])
        else:
            socketio.start_background_task(read_term, term_fd)

    @socketio.on('input', namespace='/term')
    def term_input(data):
        if term_fd is not None:
            os.write(term_fd, data.get('cmd', '').encode())
else:
    win_term_proc = None

    @socketio.on('connect', namespace='/term')
    def term_connect_win(auth):
        global win_term_proc
        cmd = _adb_cmd(["shell"])
        exe = cmd[0]
        if shutil.which(exe) is None:
            socketio.emit(
                'output',
                {'data': f"Error: cannot find adb executable '{exe}'.\n"
                         "Please install Android platform-tools or set ADB_PATH env var.\n"},
                namespace='/term'
            )
            return
        try:
            win_term_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0
            )
        except FileNotFoundError:
            socketio.emit(
                'output',
                {'data': f"Error launching adb: file not found '{exe}'.\n"},
                namespace='/term'
            )
            return

        def _read_win_output():
            while True:
                data = win_term_proc.stdout.readline()
                if not data:
                    break
                socketio.emit(
                    'output',
                    {'data': data.decode(errors='ignore')},
                    namespace='/term'
                )

        threading.Thread(target=_read_win_output, daemon=True).start()

    @socketio.on('input', namespace='/term')
    def term_input_win(data):
        cmd_bytes = data.get('cmd', '').encode()
        if win_term_proc and win_term_proc.stdin:
            try:
                win_term_proc.stdin.write(cmd_bytes)
                win_term_proc.stdin.flush()
            except BrokenPipeError:
                pass

# ------ UI namespace ------
@socketio.on("connect", namespace="/ui")
def ui_connect(auth=None):
    """
    Called when a client connects to the /ui namespace.
    Accepts an optional `auth` argument so it works under both:
      - Conda (no args)
      - Docker + eventlet (passes auth)
    """
    # ส่ง snapshot แรก (เต็ม) เมื่อต่อสาย
    pay = engine.get_payment_info()
    emit("state_delta", {
        "prog_init":  engine.prog_log,
        "sched_init": engine.sched_log,
        "payment":    pay,
        "actions":    engine.actions
    })


# @socketio.on("connect", namespace="/ui")
# # for conda
# # def ui_connect():
# # for docker
# def ui_connect(auth): 
#     # ส่ง snapshot แรก (เต็ม) เมื่อต่อสาย
#     pay = engine.get_payment_info()
#     emit("state_delta", {
#         "prog_init":  engine.prog_log,
#         "sched_init": engine.sched_log,
#         "payment":    pay,
#         "actions":    engine.actions
#     })

@app.route("/screen_size")
def screen_size():
    from utils.core import connect
    d = connect()
    w,h = d.window_size()
    return jsonify({"w": w, "h": h})

# @app.route("/screen_size")
# def screen_size():
#      from utils.screenshot import _detect_screen_width
#      w = _detect_screen_width()
#      return jsonify({"w": w})

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
