#!/usr/bin/env bash
set -euo pipefail

# AVD directory
export ANDROID_AVD_HOME=${ANDROID_AVD_HOME:-/root/.android/avd}

# ---- DHCP on eth0 if requested ----
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

# Paths and environment
export DISPLAY=${DISPLAY:-:0}
export ANDROID_SDK_ROOT=${ANDROID_SDK_ROOT:-/opt/android-sdk}
export PATH=$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/emulator:$ANDROID_SDK_ROOT/platform-tools:$PATH
TZ_NAME=${TZ:-Asia/Bangkok}

DEVICE_SERIAL=${DEVICE_SERIAL:-emulator-5554}

ADB="adb -s ${DEVICE_SERIAL}"

# Ensure VNC password exists for x11vnc
if [ ! -f /root/.vnc/passwd ]; then
  echo "[start] Creating VNC password file..."
  mkdir -p /root/.vnc
  x11vnc -storepasswd "${VNC_PASSWORD:-playflow}" /root/.vnc/passwd >/dev/null 2>&1
fi

# Sync licenses if necessary
if [ -d /opt/android/licenses ] && [ ! -d "$ANDROID_SDK_ROOT/licenses" ]; then
  echo "[start] Syncing pre-accepted licenses to SDK root"
  mkdir -p "$ANDROID_SDK_ROOT/licenses"
  cp -a /opt/android/licenses/. "$ANDROID_SDK_ROOT/licenses/"
fi

# Generate a minimal xorg.conf for dummy video driver
cat >/etc/X11/xorg.conf <<'EOF'
Section "Device"
  Identifier "Card0"
  Driver     "dummy"
  VideoRam   256000
EndSection

Section "Monitor"
  Identifier "Monitor0"
  HorizSync   28.0-80.0
  VertRefresh 48.0-75.0
EndSection

Section "Screen"
  Identifier "Screen0"
  Device     "Card0"
  Monitor    "Monitor0"
  DefaultDepth 24
  SubSection "Display"
    Depth 24
    Modes "1080x1920"
  EndSubSection
EndSection
EOF

# Remove any stale X lock file from previous runs
rm -f /tmp/.X0-lock || true

# Start Xorg (dummy)
echo "[start] Launching Xorg..."
Xorg -noreset +extension GLX +extension RANDR +extension RENDER \
     -config /etc/X11/xorg.conf :0 \
     -logfile /var/log/Xorg.log &
XORG_PID=$!

# Wait for X socket
while [ ! -S /tmp/.X11-unix/X0 ]; do sleep 1; done

# Start ADB server
echo "[start] Starting ADB server..."
adb kill-server || true
adb -a -P ${ADB_PORT:-5037} server nodaemon &
ADB_PID=$!

# Cleanup handler
cleanup() {
  echo "[start] Shutting down processes..."
  kill "$EMULATOR_PID" "$X11VNC_PID" "$NOVNC_PID" "$XORG_PID" "$ADB_PID" || true
  exit 0
}
trap cleanup SIGINT SIGTERM

# Ensure unique AVD per emulator instance
INSTANCE_NAME=${INSTANCE_NAME:-${HOSTNAME}}
BASE_AVD=${EMULATOR_DEVICE:-emu-33-playstore}
AVD_NAME="${BASE_AVD}-${INSTANCE_NAME}"

if [ ! -d "$ANDROID_AVD_HOME/${AVD_NAME}.avd" ]; then
  echo "[start] Creating AVD ${AVD_NAME}..."
  printf "no\n" | avdmanager create avd \
    -n "${AVD_NAME}" \
    -k "system-images;android-33;google_apis_playstore;x86_64" \
    --device "pixel_4" \
    --force
fi

# Remove any stale lock files that might prevent startup
find "$ANDROID_AVD_HOME/${AVD_NAME}.avd" -name '*.lock' -delete || true

# Launch emulator
echo "[start] Launching Android emulator (${AVD_NAME})..."
emulator -avd "${AVD_NAME}" \
         -gpu "${GPU:-guest}" \
         -memory "${MEMORY:-2048}" \
         -cores "${CORES:-2}" \
         -accel auto \
         -no-audio \
         -partition-size 512 \
         -verbose &
EMULATOR_PID=$!

# Give emulator a moment to start up console
sleep 5

# Start x11vnc and noVNC
echo "[start] Starting x11vnc..."
x11vnc -listen 0.0.0.0 -forever -noxdamage -shared -rfbauth /root/.vnc/passwd -display :0 -rfbport 5900 &
# x11vnc -forever -noxdamage -shared -rfbauth /root/.vnc/passwd -display :0 -rfbport 5900 &
X11VNC_PID=$!

echo "[start] Starting noVNC..."
websockify --web=/opt/noVNC 6080 localhost:5900 &
NOVNC_PID=$!

# Post-boot tasks in background
(
  echo "[post] Waiting for emulator to appear..."
  until adb devices | grep -q "^${DEVICE_SERIAL}[[:space:]]*device"; do sleep 2; done
  echo "[post] Emulator is online"

  echo "[post] Waiting for Android boot completion..."
  boot_wait=0
  until $ADB shell getprop sys.boot_completed 2>/dev/null | grep -q 1; do
    sleep 5
    boot_wait=$((boot_wait+5))
    if [ $boot_wait -ge 180 ]; then
      echo "[post] Boot not complete after 180s, proceeding anyway"
      break
    fi
  done

  echo "[post] Setting timezone & locale..."
  $ADB emu geo fix 100.5018 13.7563
  $ADB shell setprop persist.sys.timezone "$TZ_NAME" || true
  $ADB shell setprop persist.sys.locale "th-TH" || true

  echo "[post] Installing any APKs in /apks..."
  for apk in /apks/*.apk; do
    [ -e "$apk" ] || continue
    $ADB install -r "$apk" || echo "[post] Failed to install $apk"
  done

  echo "[post] Pulling /sdcard/Download..."
  mkdir -p /downloads/Download
  for f in $($ADB shell ls /sdcard/Download | tr -d '\r'); do
    $ADB pull "/sdcard/Download/$f" "/downloads/Download/$f"
  done

  SNAPSHOT_FLAG="$ANDROID_AVD_HOME/${AVD_NAME}.avd/.saved_default_snapshot"
  if [ ! -f "$SNAPSHOT_FLAG" ]; then
    echo "[post] Saving snapshot..."
    {
      echo "snapshot save default"
      sleep 1
      echo "quit"
    } | nc localhost 5554 || true
    touch "$SNAPSHOT_FLAG"
  fi

  echo "[post] Post-boot tasks complete."
) &

# Wait indefinitely
wait "$EMULATOR_PID"
