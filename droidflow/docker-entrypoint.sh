#!/usr/bin/env bash
set -euo pipefail

# Request a LAN IP via DHCP on macvlan interface (eth0)
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

# If arguments are provided, run them instead of the default
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# Attempt to connect local adb server to the emulator
if [ -n "${INSTANCE_NAME:-}" ]; then
  echo "[start] Connecting adb to ${INSTANCE_NAME}:5555..."
  attempt=0
  until adb connect "${INSTANCE_NAME}:5555" >/dev/null 2>&1; do
    attempt=$((attempt+1))
    if [ "$attempt" -ge 5 ]; then
      echo "[start] adb connect failed after $attempt attempts"
      break
    fi
    sleep 2
  done
fi

# Default: launch the Flask app
exec python3 /app/app.py