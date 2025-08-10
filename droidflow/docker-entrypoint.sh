#!/usr/bin/env bash
set -euo pipefail

# ขอ IP จาก DHCP (macvlan ใช้ eth0 ในคอนเทนเนอร์)
if [ "${FORCE_DHCP:-0}" = "1" ]; then
  echo "[start] Releasing any existing DHCP lease..."
  dhclient -r eth0 || true
  echo "[start] Requesting DHCP on eth0..."
  attempt=0
  # Try up to 5 times to obtain a lease before giving up
  until dhclient -v -1 eth0; do
    attempt=$((attempt+1))
    if [ "$attempt" -ge 5 ]; then
      echo "[start] dhclient failed after $attempt attempts"
      break
    fi
    sleep 5
  done
fi

# ถ้ามีอาร์กิวเมนต์ -> รันคำสั่งนั้นแทน
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# ค่าเริ่มต้น: รันแอป Flask
exec python3 /app/app.py