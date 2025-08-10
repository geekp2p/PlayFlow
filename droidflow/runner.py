#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time
import re
import xml.etree.ElementTree as ET
from utils import (
    connect,
    log,
    el_matches,
    node_at,
    actions,
    wait_for_el,
    wait_for_text,
)

# ──────────── coordinate helper ────────────
def _xy_to_px(d, x, y):
    """Convert normalized or absolute x,y to pixel coordinates."""
    w, h = d.window_size()
    px = int(x * w) if 0 <= x <= 1 else int(x)
    py = int(y * h) if 0 <= y <= 1 else int(y)
    return px, py

# ────── post-click check ───────
def _post_click_check(d, px, py, expected_bounds):
    """After click, verify element still there or report disappearance/resize."""
    try:
        time.sleep(0.5)
        root = ET.fromstring(d.dump_hierarchy())
        n = node_at(root, px, py)
        if not n:
            log("⚠ element disappeared after click")
        elif expected_bounds and n.get('bounds') != expected_bounds:
            log(f"⚠ bounds changed {expected_bounds} -> {n.get('bounds')}")
    except Exception as e:
        log(f"post-click check fail {e}")

# ────── click implementation ───────
def do_click(d, a, mode):
    """
    Try 1) selector-based click (if mode!='position'),
        2) click at midpoint of bounds,
        3) click at raw x/y.
    """
    # 1) selector
    if mode != "position":
        for key, kw in (("rid","resourceId"), ("text","text"), ("desc","description")):
            v = a.get(key)
            if v:
                try:
                    getattr(d, kw)(v).click()
                    return
                except:
                    pass

    # 2) bounds
    bounds = a.get("bounds")
    if bounds:
        l, t, r, b = map(int, re.findall(r"\d+", bounds))
        px, py = (l + r)//2, (t + b)//2
        d.click(px, py)
        _post_click_check(d, px, py, bounds)
        return

    # 3) raw coords
    if "x" in a and "y" in a:
        px, py = _xy_to_px(d, a["x"], a["y"])
        d.click(px, py)
        _post_click_check(d, px, py, None)
        return

    log("⚠ do_click(): no selector/bounds to click")

# ──────── main flow runner ────────
def run_flow(acts_list, mode):
    d = connect()
    pc = 0
    # build label → index map
    labels = {a.get("val"): i for i, a in enumerate(acts_list) if a.get("op") == "label"}
    stack = []
    log(f"RUN mode={mode}")

    while pc < len(acts_list):
        a = acts_list[pc]
        op = a.get("op")

        if   op == "wait":
            time.sleep(a.get("sec", 0))
        elif op == "click":
            do_click(d, a, mode)
        elif op == "key":
            d.press(a.get("key"))
        elif op == "type":
            d.shell(f'input text "{a.get("text","")}"')

        elif op == "swipe":
            direction = a.get("dir", "left")
            # ปรับ swipe ให้เริ่มและสิ้นสุดในโซนกลาง (30%–70%) ของหน้าจอ
            if direction == "right":
                d.swipe(0.3, 0.5, 0.7, 0.5, 0.3)
            elif direction == "left":
                d.swipe(0.7, 0.5, 0.3, 0.5, 0.3)
            elif direction == "down":
                d.swipe(0.5, 0.4, 0.5, 0.6, 0.3)
            elif direction == "up":
                d.swipe(0.5, 0.6, 0.5, 0.4, 0.3)
            else:
                d.swipe(0.7, 0.5, 0.3, 0.5, 0.3)


        # elif op == "swipe":
        #     direction = a.get("dir", "left")
        #     # ย้ายทุก swipe มาไว้ใน bottom 30% ของหน้าจอ (y: 70%–100%)
        #     if direction == "right":
        #         d.swipe(0.15, 0.85, 0.85, 0.85, 0.3)
        #     elif direction == "left":
        #         d.swipe(0.85, 0.85, 0.15, 0.85, 0.3)
        #     elif direction == "down":
        #         d.swipe(0.5, 0.75, 0.5, 0.95, 0.3)
        #     elif direction == "up":
        #         d.swipe(0.5, 0.95, 0.5, 0.75, 0.3)
        #     else:
        #         d.swipe(0.85, 0.85, 0.15, 0.85, 0.3)
    

        # elif op == "swipe":
        #     direction = a.get("dir", "left")
        #     if direction == "right":
        #         d.swipe(0.1, 0.5, 0.9, 0.5, 0.3)
        #     elif direction == "up":
        #         d.swipe(0.5, 0.9, 0.5, 0.1, 0.3)
        #     elif direction == "down":
        #         d.swipe(0.5, 0.1, 0.5, 0.9, 0.3)
        #     else:
        #         d.swipe(0.9, 0.5, 0.1, 0.5, 0.3)


        elif op == "wait_el":
            sel = {k: a.get(k) for k in ("rid", "text", "desc") if a.get(k)}
            wait_for_el(sel, float(a.get("timeout", 10)))
        elif op == "wait_text":
            wait_for_text(a.get("text", ""), float(a.get("timeout", 10)))
        elif op == "assert":
            ok = el_matches(d, a)
            if ok:
                log(f"✔ assert {a.get('sel')} OK")
            else:
                log(f"✖ assert {a.get('sel')} FAIL")
        elif op == "loop_start":
            stack.append({"pos": pc, "cnt": int(a.get("val", 1))})
        elif op == "loop_end":
            top = stack[-1]
            top["cnt"] -= 1
            if top["cnt"] > 0:
                pc = top["pos"]
            else:
                stack.pop()
        elif op == "if_start":
            # TODO: implement skipping to matching if_end on false
            pass
        elif op == "goto":
            pc = labels.get(a.get("val"), pc)

        pc += 1
        time.sleep(0.12)

    log("END")

# ──────── spawning helpers ────────
def run_now(mode="hybrid"):
    """Run the current recorded actions immediately."""
    threading.Thread(target=run_flow, args=(actions.copy(), mode), daemon=True).start()

def run_compile(acts_list, mode="hybrid"):
    """Run a provided list of actions (e.g. compiled flow)."""
    threading.Thread(target=run_flow, args=(acts_list, mode), daemon=True).start()