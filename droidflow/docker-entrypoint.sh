#!/usr/bin/env bash
set -euo pipefail

# Use the ADB server running inside the emulator container.
# Export variables understood by both the adb CLI and the Python adbutils
# library.  If the user provides ADB_SERVER_SOCKET, derive host/port from it;
# otherwise fall back to the default emulator container location.
export ADB_SERVER_SOCKET="${ADB_SERVER_SOCKET:-tcp:pf_emulator:5037}"
if [[ "$ADB_SERVER_SOCKET" == tcp:* ]]; then
  hostport="${ADB_SERVER_SOCKET#tcp:}"
  export ADB_SERVER_HOST="${ADB_SERVER_HOST:-${hostport%%:*}}"
  export ADB_SERVER_PORT="${ADB_SERVER_PORT:-${hostport##*:}}"
  export ANDROID_ADB_SERVER_HOST="${ANDROID_ADB_SERVER_HOST:-$ADB_SERVER_HOST}"
  export ANDROID_ADB_SERVER_PORT="${ANDROID_ADB_SERVER_PORT:-$ADB_SERVER_PORT}"
fi

# Prefer the platform-tools adb bundled in the image
export PATH="/opt/android-sdk/platform-tools:${PATH}"
export ADB_PATH="${ADB_PATH:-/opt/android-sdk/platform-tools/adb}"

# Wait until a device appears on the remote ADB server
echo "[entry] Waiting for emulator device on ${ANDROID_ADB_SERVER_HOST}:${ANDROID_ADB_SERVER_PORT} ..."
attempt=0
ser=""
until ser="$(adb devices | awk '/device$/ {print $1; exit}')"; do
  attempt=$((attempt+1))
  if [ "$attempt" -ge 60 ]; then
    echo "[entry] WARN: no device found from 'adb devices'"
    break
  fi
  sleep 2
done

if [ -n "$ser" ]; then
  export DEVICE_SERIAL="$ser"
  echo "[entry] Using DEVICE_SERIAL=$DEVICE_SERIAL"

fi

# Request a LAN IP via DHCP on macvlan interface (eth0) when asked
if [ "${FORCE_DHCP:-0}" = "1" ]; then
  echo "[start] Releasing any existing DHCP lease..."
  dhclient -r eth0 || true
  echo "[start] Requesting DHCP on eth0..."
  attempt=0
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

# Default: launch the Flask app
exec python3 /app/app.py
