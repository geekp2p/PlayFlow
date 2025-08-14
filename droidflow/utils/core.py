#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core utilities for DroidFlow.

รองรับ 2 โหมดหลัก:
  • Dev/Conda (Windows/macOS/Linux) – USB หรือ emulator local
  • Docker (shared network namespace กับ container emulator) – auto detect

Strategy การเลือก device:
  1) ADB_SERVER_SOCKET=tcp:<host>:<port>  → query adb server นั้น → pick serial
  2) serial argument (connect(serial="..."))
  3) ?serial=... ใน Flask request
  4) env DEVICE_SERIAL (อ่านสดทุกครั้ง)
  5) first 'device' จาก `adb devices`
  6) no-arg u2.connect() fallback
"""

import os

# Derive host/port env vars from ADB_SERVER_SOCKET before importing libraries
_adb_sock = os.getenv("ADB_SERVER_SOCKET")
if _adb_sock and _adb_sock.startswith("tcp:"):
    _hostport = _adb_sock[4:]
    if ":" in _hostport:
        _host, _port = _hostport.split(":", 1)
    else:
        _host, _port = _hostport, "5037"
    os.environ.setdefault("ADB_SERVER_HOST", _host)
    os.environ.setdefault("ADB_SERVER_PORT", _port)
    os.environ.setdefault("ANDROID_ADB_SERVER_HOST", _host)
    os.environ.setdefault("ANDROID_ADB_SERVER_PORT", _port)

import json
import re
import time
import subprocess
from datetime import datetime
import xml.etree.ElementTree as ET
import uiautomator2 as u2
from flask import has_request_context, request

# ───────────── config ─────────────
DEVICE_SERIAL_DEFAULT = os.getenv("DEVICE_SERIAL")  # อ่านครั้งแรก; อาจมีการ export ภายหลัง
# Default to the platform-tools adb installed inside the container if available
ADB_PATH = os.getenv("ADB_PATH", "/opt/android-sdk/platform-tools/adb")
INSTANCE_NAME = os.getenv("INSTANCE_NAME")
ADB_CONNECT_PORT = os.getenv("ADB_CONNECT_PORT", "5556")

# ───────────── runtime env helpers ─────────────
def _current_device_serial() -> str | None:
    """อ่าน DEVICE_SERIAL สดจาก env ทุกครั้ง."""
    return os.environ.get("DEVICE_SERIAL", DEVICE_SERIAL_DEFAULT)

def _adb_cmd(extra: list[str], *, include_serial: bool = True) -> list[str]:
    """
    Construct an ``adb`` command honoring ``DEVICE_SERIAL`` and any remote
    ADB server settings.

    Parameters
    ----------
    extra:
        Additional arguments to append to the command.
    include_serial:
        When ``False`` the ``-s <serial>`` flag is omitted.  This is useful for
        commands such as ``adb devices`` which must query *all* devices rather
        than a single, potentially stale serial.
    """

    base = [ADB_PATH]

    # honour ADB_SERVER_SOCKET for remote servers, e.g. ``tcp:host:port``
    adb_sock = os.getenv("ADB_SERVER_SOCKET")
    if adb_sock and adb_sock.startswith("tcp:"):
        hostport = adb_sock[4:]
        if ":" in hostport:
            host, port = hostport.split(":", 1)
        else:
            host, port = None, hostport
        if host:
            base += ["-H", host]
        if port:
            base += ["-P", port]

    if include_serial:
        ser = _current_device_serial()
        if ser:
            base += ["-s", ser]
    return base + extra

def _pick_first_device_from_adb(host: str | None = None, port: str | None = None) -> str | None:
    """
    query adb server (default หรือ host:port) แล้วคืน serial ตัวแรกที่ state == device.
    """
    cmd = [ADB_PATH]
    if host:
        cmd += ["-H", host]
    if port:
        cmd += ["-P", port]
    cmd += ["devices"]
    try:
        out = subprocess.check_output(cmd, text=True, timeout=3, errors="ignore")
    except Exception:
        return None

    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\S+)\s+device$", line)
        if m:
            return m.group(1)
    return None
    
def ensure_device_online(timeout: int = 30, interval: float = 1.0) -> str | None:
    """Ensure there is a connected device; update DEVICE_SERIAL if found.

    This polls ``adb devices`` (optionally running ``adb connect`` each loop) until
    a device in the ``device`` state is discovered or the timeout expires.
    Returns the device serial if found, otherwise ``None``.
    """

    ser = _current_device_serial()
    # if not ser:
    #     return
    out = ""
    # try:
    #     out = subprocess.check_output(
    #         _adb_cmd(["devices"]), text=True, timeout=3, errors="ignore"
    #     )
    #     if ser and re.search(rf"^{re.escape(ser)}\s+device$", out, re.M):
    #         return ser
    # except Exception:
    #     out = ""
    host = INSTANCE_NAME
    adb_sock = os.getenv("ADB_SERVER_SOCKET")
    deadline = time.time() + timeout

    while time.time() < deadline:
        if host and not adb_sock:
            subprocess.run(
                [ADB_PATH, "connect", f"{host}:{ADB_CONNECT_PORT}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

    # if host and not adb_sock:
    
    # Always attempt to connect to the emulator if a host is provided and we're
    # using the local ADB server. This supports containerized setups where the
    # device isn't pre-attached.
    # if host and not adb_sock:    
    #     subprocess.run(
    #         [ADB_PATH, "connect", f"{host}:{ADB_CONNECT_PORT}"],
    #         stdout=subprocess.DEVNULL,
    #         stderr=subprocess.DEVNULL,
    #         check=False,
    #     )
    #     time.sleep(1)
        # try:
        #     out = subprocess.check_output(
        #         _adb_cmd(["devices"]), text=True, timeout=3, errors="ignore"
        #     )
        #     if ser and re.search(rf"^{re.escape(ser)}\s+device$", out, re.M):
        #         return ser
        # except Exception:
        #     out = ""
        try:
            out = subprocess.check_output(
                _adb_cmd(["devices"], include_serial=False),
                text=True,
                timeout=3,
                errors="ignore",
            )
        except Exception:
            out = ""

        if ser and re.search(rf"^{re.escape(ser)}\s+device$", out, re.M):
            return ser

        # No match for current serial; attempt to pick the first available
        for line in out.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^(\S+)\s+device$", line)
            if m:
                new_ser = m.group(1)
                os.environ["DEVICE_SERIAL"] = new_ser
                return new_ser

        time.sleep(interval)

    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\S+)\s+device$", line)
        if m:
            new_ser = m.group(1)
            os.environ["DEVICE_SERIAL"] = new_ser
            return new_ser
    return None

def connect(serial: str | None = None):
    """Return uiautomator2.Device following the priority rules."""
    ser_env = ensure_device_online()

    # 1) honor ADB_SERVER_SOCKET
    adb_sock = os.getenv("ADB_SERVER_SOCKET")
    if adb_sock and adb_sock.startswith("tcp:"):
        hostport = adb_sock[4:]
        if ":" in hostport:
            host, port = hostport.split(":", 1)
        else:
            host, port = None, hostport
        pick = _pick_first_device_from_adb(host, port)
        if pick and serial is None:
            serial = pick
    if serial is None and ser_env:
        serial = ser_env            
    # 2) request param (เฉพาะเมื่อไม่มี arg)
    if serial is None and has_request_context():
        reqser = request.args.get("serial")
        if reqser:
            serial = reqser
    # 3) env
    if serial is None:
        serial = _current_device_serial()
    # 4) default adb search
    if not serial:
        serial = _pick_first_device_from_adb()

    # connect attempts
    try:
        if serial:
            return u2.connect(serial)
        return u2.connect()
    except Exception:
        try:
            if serial:
                return u2.connect_usb(serial)
        except Exception:
            pass
        if serial:
            try:
                return u2.connect(f"adb://{serial}")
            except Exception:
                pass
        try:
            return u2.connect()
        except Exception as e:
            raise RuntimeError("Unable to connect to any device") from e

# ───────────── paths ─────────────
FLOW_DIR = "./flows"
os.makedirs(FLOW_DIR, exist_ok=True)

# ─────────── runtime state ───────────
recording = False       # are we recording
_last_ts = None         # timestamp of last recorded action
actions = []            # current recorded actions
prog_log = []           # program log lines
sched_log = []          # scheduler log lines

# ────────────── misc helpers ──────────────
def log(msg: str, dest: str = "prog"):
    """Append a timestamped message to prog_log or sched_log."""
    ts = datetime.utcnow().strftime("%H:%M:%S")
    tgt = prog_log if dest == "prog" else sched_log
    tgt.append(f"{ts} {msg}")
    if len(tgt) > 200:
        tgt.pop(0)

def ts_now() -> str:
    """Return current UTC time as HH:MM:SS string."""
    return datetime.utcnow().strftime("%H:%M:%S")

def inside(a: list[int], b: list[int]) -> bool:
    """Return True if rectangle a is entirely inside rectangle b."""
    return a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]

def _adb(cmd: list[str]):
    """Run adb command without raising on failure."""
    ensure_device_online()
    subprocess.run(_adb_cmd(cmd), check=False)

# ──────────── foreground helper ────────────
def current_app() -> dict:
    """Return {'package': str, 'activity': str} for foreground app."""
    try:
        info = connect().app_current() or {}
        if info.get("package"):
            return info
    except Exception as e:
        log(f"current_app u2 fail {e}")
    try:
        out = subprocess.check_output(
            _adb_cmd(["shell", "dumpsys", "window", "windows"]),
            text=True, timeout=2, errors="ignore"
        )
        m = re.search(r"mCurrentFocus.*? (.+?)/(.+?) ", out)
        if m:
            return {"package": m.group(1), "activity": m.group(2)}
    except Exception as e:
        log(f"current_app dumpsys fail {e}")
    return {}

# ───────────── payment helper ─────────────
def read_payment_info() -> dict:
    """Extract payment info from current UI hierarchy.

    Falls back to empty values when a device is unavailable.
    """
    try:
        xml = connect().dump_hierarchy(compressed=False, pretty=True)
    except Exception as e:  # device might be offline
        log(f"read_payment_info fail {e}")
        return {'amount': None, 'is_new': False, 'name': ''}
    
    root = ET.fromstring(xml)
    parent_map = {c: p for p in root.iter('node') for c in p}
    for n in root.iter('node'):
        txt = (n.get('text') or '').strip()
        m = re.match(r'^(\+?)(\d+(?:\.\d+)?)$', txt)
        if m:
            return {
                'amount': float(m.group(2)),
                'is_new': bool(m.group(1)),
                'name': _extract_name(n, parent_map)
            }
    return {'amount': None, 'is_new': False, 'name': ''}

def _extract_name(node, parent_map):
    parent = parent_map.get(node)
    if parent:
        for sib in parent:
            t = (sib.get('text') or '').strip()
            if t and not re.match(r'^(\+?)(\d+(?:\.\d+)?)$', t):
                return t
    return ''

# ───────────── element helpers ─────────────
def first_info(n: ET.Element) -> bool:
    """Return True if node has identifying info."""
    return any(n.get(k) for k in ('resource-id','text','content-desc'))

def node_at(root: ET.Element, px: int, py: int) -> ET.Element | None:
    """Find smallest clickable node containing (px,py)."""
    best, area = None, float('inf')
    for n in root.iter('node'):
        if n.get('clickable') != 'true':
            continue
        bounds = list(map(int, re.findall(r'\d+', n.get('bounds') or '')))
        if len(bounds) == 4:
            l, t, r, b = bounds
            if l <= px <= r and t <= py <= b:
                a = (r - l) * (b - t)
                if a < area:
                    best, area = n, a
    return best

def el_matches(d, a, tol_px: int = 15) -> bool:
    """Check selector match and bounds proximity."""
    sel = a.get('sel', {})
    node = None
    for key, kw in [('rid','resourceId'),('text','text'),('desc','description')]:
        v = sel.get(key)
        if not v:
            continue
        try:
            c = getattr(d, kw)(v)
            if c.exists:
                node = c
                break
        except Exception:
            pass
    if not node or not node.exists:
        return False
    if not a.get('bounds'):
        return True
    exp = list(map(int, re.findall(r'\d+', a['bounds'])))
    cur = list(map(int, re.findall(r'\d+', node.info.get('bounds',''))))
    if len(exp) != 4 or len(cur) != 4:
        return False
    cx, cy = (exp[0]+exp[2])//2, (exp[1]+exp[3])//2
    dx, dy = (cur[0]+cur[2])//2, (cur[1]+cur[3])//2
    return abs(cx-dx) <= tol_px and abs(cy-dy) <= tol_px

# ───────────── waiting helpers ─────────────
def wait_for_el(sel: dict, timeout: float = 10.0, interval: float = 0.5) -> bool:
    d = connect(); end = time.time() + timeout
    while time.time() < end:
        try:
            if el_matches(d, {'sel': sel}):
                return True
        except Exception as e:
            log(f"wait_for_el fail {e}")
        time.sleep(interval)
    return False

def wait_for_text(text: str, timeout: float = 10.0, interval: float = 0.5) -> bool:
    d = connect(); end = time.time() + timeout
    while time.time() < end:
        try:
            if text in d.dump_hierarchy(compressed=False, pretty=True):
                return True
        except Exception as e:
            log(f"wait_for_text fail {e}")
        time.sleep(interval)
    return False

def sleep_if_needed():
    global _last_ts
    if _last_ts is None:
        _last_ts = time.time()
        return
    dt = time.time() - _last_ts
    if dt >= 0.05:
        actions.append({'op':'wait','sec':round(dt,3)})
    _last_ts = time.time()

# ───────────── actions & flows ─────────────
def get_elements() -> list[dict]:
    d = connect()
    root = ET.fromstring(d.dump_hierarchy(compressed=False, pretty=True))
    raw = [(list(map(int, re.findall(r'\d+', n.get('bounds') or ''))), n)
           for n in root.iter('node') if n.get('clickable') == 'true']
    keep = [n for i,(b1,n) in enumerate(raw)
            if not any(i!=j and inside(b1,b2) for j,(b2,_) in enumerate(raw))]
    return [{
        'bounds': n.get('bounds') or '',
        'rid': n.get('resource-id') or '',
        'text': n.get('text') or '',
        'desc': n.get('content-desc') or '',
        'cls': n.get('class') or ''
    } for n in keep]

def start_record():
    global recording, _last_ts
    if not recording:
        recording = True
        _last_ts = time.time()
        actions.append({'op':'rec','state':True,'t':ts_now()})

def stop_record():
    global recording
    if recording:
        recording = False
        actions.append({'op':'rec','state':False,'t':ts_now()})

def clear_actions():
    actions.clear()

def record_click(args):
    global _last_ts
    x, y = float(args.get('x', 0)), float(args.get('y', 0))
    d = connect()
    w, h = d.window_size()
    px, py = int(x * w), int(y * h)
    d.click(px, py)

    sel = {}
    try:
        root = ET.fromstring(d.dump_hierarchy(compressed=False, pretty=True))
        n = node_at(root, px, py)
        if n:
            for k in ['resource-id', 'text', 'content-desc']:
                v = n.get(k)
                if v:
                    sel[k.replace('-', '_')] = v
            sel['bounds'] = n.get('bounds') or ''
    except Exception as e:
        log(f"inspect fail {e}")

    log(f"🖱 click x={x:.4f} y={y:.4f} sel={sel}")

    if recording:
        sleep_if_needed()
        row = {'op':'click','x':round(x,4),'y':round(y,4)}
        row.update(sel)
        actions.append(row)

def inspect_element(args) -> dict:
    x, y = float(args.get('x', 0)), float(args.get('y', 0))
    d = connect()
    w, h = d.window_size()
    px, py = int(x * w), int(y * h)
    info: dict = {}
    try:
        xml = d.dump_hierarchy(compressed=False, pretty=True)
        root = ET.fromstring(xml)
        n = node_at(root, px, py)
        if not n:
            candidates: list[tuple[int, ET.Element]] = []
            for m in root.iter('node'):
                nums = re.findall(r"\d+", m.get('bounds') or '')
                if len(nums) == 4:
                    l, t, r2, b2 = map(int, nums)
                    if l <= px <= r2 and t <= py <= b2:
                        area = (r2 - l) * (b2 - t)
                        candidates.append((area, m))
            if candidates:
                n = min(candidates, key=lambda x: x[0])[1]
        if n:
            if not first_info(n):
                parent_map = {c: p for p in root.iter('node') for c in p}
                cur = n
                while (cur := parent_map.get(cur)) and not first_info(cur):
                    pass
                n = cur or n
            info = {k: n.get(k) or '' for k in ['resource-id','text','content-desc','class','bounds']}
    except Exception as e:
        log(f"inspect fail {e}")
    return info

def inspect_element_raw(args) -> dict:
    x, y = float(args.get('x', 0)), float(args.get('y', 0))
    d = connect()
    w, h = d.window_size()
    px, py = int(x * w), int(y * h)
    info = {}
    try:
        xml = d.dump_hierarchy(compressed=False, pretty=True)
        root = ET.fromstring(xml)
        candidates = []
        for n in root.iter('node'):
            nums = re.findall(r'\d+', n.get('bounds') or '')
            if len(nums)==4:
                l, t, r2, b2 = map(int, nums)
                if l <= px <= r2 and t <= py <= b2:
                    area = (r2-l)*(b2-t)
                    candidates.append((area, n))
        if candidates:
            n = min(candidates, key=lambda x: x[0])[1]
            if not first_info(n):
                parent_map = {c:p for p in root.iter('node') for c in p}
                cur = n
                while (cur := parent_map.get(cur)) and not first_info(cur):
                    pass
                n = cur or n
            info = {k: n.get(k) or '' for k in ('resource-id','text','content-desc','class','bounds')}
    except Exception as e:
        log(f"inspect_raw fail {e}")
    return info

def record_key(args):
    key = args.get('key', 'home')
    codes = {
        'home': '3',
        'back': '4',
        'recent': '187',
        'volume_up': '24',
        'volume_down': '25',
        'power': '26'
    }
    subprocess.run(_adb_cmd(['shell','input','keyevent', codes.get(key, key)]), check=False)
    if recording:
        sleep_if_needed()
        actions.append({'op':'key','key':key})

def record_block(args):
    kind = args.get('kind')
    val  = args.get('val','')
    if not recording:
        return
    sleep_if_needed()
    row = {'op':kind}
    if val:
        row['val'] = val
    actions.append(row)

def record_type(args):
    txt = args.get('txt','')
    connect().shell(f'input text "{txt}"')
    if recording:
        sleep_if_needed()
        actions.append({'op':'type','text':txt})

def record_swipe(args):
    dir = args.get('dir','left')
    d = connect()
    funcs = {
        'right': (0.3, 0.5, 0.7, 0.5, 0.3),
        'left':  (0.7, 0.5, 0.3, 0.5, 0.3),
        'down':  (0.5, 0.4, 0.5, 0.6, 0.3),
        'up':    (0.5, 0.6, 0.5, 0.4, 0.3),
    }
    d.swipe(*funcs.get(dir, funcs['left']))
    if recording:
        sleep_if_needed()
        actions.append({'op':'swipe','dir':dir})

def flow_path(name: str) -> str:
    return os.path.join(FLOW_DIR, f"{name}.flow")

def save_flow(payload: dict):
    name = payload.get('name','flow')
    acts = payload.get('actions',[])
    with open(flow_path(name),'w',encoding='utf-8') as f:
        for a in acts:
            f.write(json.dumps(a,ensure_ascii=False)+'\n')

def load_flow(name: str) -> dict:
    try:
        with open(flow_path(name),encoding='utf-8') as f:
            acts=[json.loads(l) for l in f]
        actions.clear(); actions.extend(acts)
        return {'ok':True,'actions':acts}
    except FileNotFoundError:
        return {'ok':False,'error':'notfound'}

def get_transactions() -> list[dict]:
    root=ET.fromstring(connect().dump_hierarchy(compressed=False,pretty=True))
    pm={c:p for p in root.iter('node') for c in p}
    tx=[]
    for n in root.iter('node'):
        t=(n.get('text') or '').strip()
        if not t.endswith('จ่ายแล้ว'):
            continue
        cont=pm.get(n)
        if not cont:
            continue
        texts=[s.get('text') or '' for s in cont]
        if not any(re.search(r'[\+\-]?\d+(?:\.\d+)?',x) for x in texts):
            cont=pm.get(cont,cont)
        tm=''; amt=''
        for s in cont.iter('node'):
            s_txt=(s.get('text') or '').strip()
            if not tm:
                m=re.search(r'\b(\d{1,2}:\d{2})\b',s_txt)
                if m: tm=m.group(1)
            if not amt:
                m2=re.search(r'([\+\-]?\d+(?:\.\d+)?)',s_txt.replace('฿',''))
                if m2 and not re.search(r'\b\d{1,2}:\d{2}\b',s_txt):
                    amt=m2.group(1)
            if tm and amt:
                break
        tx.append({'name':t,'time':tm,'amount':amt,'bounds':cont.get('bounds')or''})
    return tx

def get_main_activity(pkg: str) -> tuple[bool,str]:
    try:
        res=subprocess.check_output(_adb_cmd(['shell','cmd','package','resolve-activity','--brief',pkg]),
                                    text=True,timeout=2).splitlines()
        return True,res[-1] if res else ('',)
    except Exception as e:
        log(f"pkginfo {pkg} fail {e}")
    return False,''

def is_app_running(pkg: str) -> bool:
    try:
        return bool(subprocess.check_output(_adb_cmd(['shell','pidof',pkg]),text=True).strip())
    except Exception:
        return False

def open_app(pkg: str) -> tuple[bool,str]:
    if not pkg:
        return False,'no pkg'
    log(f"open {pkg}")
    ok,_=get_main_activity(pkg)
    if not ok:
        return False,'package not found'
    try:
        d=connect(); d.app_start(pkg,wait=True,stop=True)
        cur=connect().app_current().get('package')
        return (cur==pkg),'running' if cur==pkg else f'fg={cur}'
    except Exception as e:
        log(f"open {pkg} fail {e}")
        return False,str(e)

def close_app(pkg: str) -> tuple[bool,str]:
    if not pkg:
        return False,'no pkg'
    log(f"close {pkg}")
    try:
        d=connect(); d.app_stop(pkg); time.sleep(0.8)
        cur=current_app().get('package')
        return (cur!=pkg),'stopped' if cur!=pkg else f'fg={cur}'
    except Exception as e:
        log(f"close {pkg} fail {e}")
        return False,str(e)

def restart_app(pkg: str, mode: str = 'safe') -> tuple[bool,str]:
    """Close and reopen an app. If mode=='force' use adb force-stop."""
    if not pkg:
        return False,'no pkg'
    if mode=='force':
        _adb_cmd(['shell','am','force-stop',pkg])
    else:
        close_app(pkg)
    time.sleep(0.8)
    return open_app(pkg)