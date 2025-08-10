#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import socketio, app

if __name__ == "__main__":
    # วิ่งบนพอร์ตเดิม (5000) ก็ได้ หรือจะเปลี่ยนเป็น 5001 ก็ได้ ตามสะดวก
    socketio.run(app, host="0.0.0.0", port=5000)