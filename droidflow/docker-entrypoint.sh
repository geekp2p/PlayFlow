#!/usr/bin/env sh
set -e

# Request IP via DHCP if requested
if [ "${FORCE_DHCP:-0}" = "1" ]; then
  echo "[start] Releasing any existing DHCP lease..."
  dhclient -r eth0 || true
  echo "[start] Requesting DHCP on eth0..."
  dhclient -v eth0 || echo "[start] dhclient failed"
fi

# If command-line arguments are supplied, run them
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# Default: launch the DroidFlow Flask application
exec python3 /app/app.py