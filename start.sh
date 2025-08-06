# start.sh
#!/bin/bash
set -e

# obtain IP from Mikrotik via DHCP if requested
if [ "${FORCE_DHCP:-0}" = "1" ]; then
  ip addr flush dev eth0 || true
  dhclient -v eth0 || true
fi

# start android emulator in background
emulator -avd emu-33-playstore \
  -no-window -no-audio \
  -gpu swiftshader_indirect \
  -verbose &

# wait a little for emulator to boot
sleep 5

# launch PlayFlow web UI
exec python3 android.py
