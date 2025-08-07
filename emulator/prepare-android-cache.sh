#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------------------------------------------
# prepare-android-cache.sh - download/install Android command-line tools,
#                            ensure required system image is present, and
#                            pre-accept licenses if possible.
# ----------------------------------------------------------------------------

CACHE_ROOT=${ANDROID_SDK_ROOT:-/opt/android-sdk}
CMDLINE_TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip"

export ANDROID_SDK_ROOT="$CACHE_ROOT"
export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/emulator:$ANDROID_SDK_ROOT/platform-tools:$PATH"

MARKER="$CACHE_ROOT/.complete"
TMP_ZIP="/tmp/cmdline.zip"
LICENSE_LOG="/var/log/accept_licenses.log"

# ensure base dirs + perms
mkdir -p "$ANDROID_SDK_ROOT"
chmod -R u+rx "$ANDROID_SDK_ROOT" || true

# skip if already done
if [ -f "$MARKER" ] && [ -d "$ANDROID_SDK_ROOT/platform-tools" ]; then
  echo "Android SDK cache already prepared, skipping."
  exit 0
fi

echo "Preparing Android SDK cache at $CACHE_ROOT"

# download command-line tools
echo "Downloading command-line tools..."
curl --fail --location --retry 3 --retry-delay 5 "$CMDLINE_TOOLS_URL" -o "$TMP_ZIP"

# unpack
unzip -q "$TMP_ZIP" -d "$ANDROID_SDK_ROOT/cmdline-tools"
rm -f "$TMP_ZIP"
mv "$ANDROID_SDK_ROOT/cmdline-tools/cmdline-tools" "$ANDROID_SDK_ROOT/cmdline-tools/latest"
chmod -R u+rx "$ANDROID_SDK_ROOT/cmdline-tools/latest/bin"

# wait for sdkmanager
SDKMANAGER_CMD="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"
echo "Updating SDK manager..."
"$SDKMANAGER_CMD" --update || echo "[WARN] sdkmanager --update failed"

# accept licenses
echo "Accepting licenses..."
yes | "$SDKMANAGER_CMD" --licenses >> "$LICENSE_LOG" 2>&1 || true

# install core components
echo "Installing platform-tools, emulator, system-image..."
yes | "$SDKMANAGER_CMD" \
    "platform-tools" \
    "emulator" \
    "system-images;android-33;google_apis_playstore;x86_64" || true

# สร้าง AVD ถ้ายังไม่มี
if ! avdmanager list avd | grep -q "^${EMULATOR_DEVICE}$"; then
  echo "Creating AVD ${EMULATOR_DEVICE}…"
  # ตอบ "no" (don’t use custom hardware profile)
  printf "no\n" | avdmanager create avd \
    -n "${EMULATOR_DEVICE}" \
    -k "system-images;android-33;google_apis_playstore;x86_64" \
    --force
else
  echo "AVD ${EMULATOR_DEVICE} already exists, skip creation."
fi

# mark done
touch "$MARKER"
echo "Android SDK cache prepared at $CACHE_ROOT"
