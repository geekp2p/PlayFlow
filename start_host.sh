#!/usr/bin/env bash
set -euo pipefail

# start_host.sh - Prepare host and containers for PlayFlow with ADB inside container
# 1. Stop host-side ADB server to avoid port conflicts
# 2. Start Docker containers
# 3. Launch ADB server inside pf_droidflow container, connect to emulator, and reverse port 5000

# Kill host ADB server if present (suppress warning if it's not running)
if command -v adb >/dev/null 2>&1; then
  adb kill-server >/dev/null 2>&1 || true
fi

# Start containers
docker compose up -d

# Ensure ADB inside droidflow container is clean
docker exec pf_droidflow adb kill-server >/dev/null 2>&1 || true

docker exec pf_droidflow adb start-server

# Connect droidflow's ADB to the emulator and list devices
docker exec pf_droidflow adb connect pf_emulator:5555 >/dev/null 2>&1 || true
docker exec pf_droidflow adb devices

# Reverse port 5000 so apps in device can reach container service
# (container port 5000 is already exposed to host)
docker exec pf_droidflow adb reverse tcp:5000 tcp:5000

cat <<EOM
Containers started. ADB is running inside pf_droidflow.
Port 5000 is reversed for device -> container access.
EOM