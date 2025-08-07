#!/usr/bin/env bash
set -euo pipefail

CACHE_ROOT=${ANDROID_SDK_ROOT:-/opt/android-sdk}
CMDLINE_TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip"
MARKER="$CACHE_ROOT/.complete"
TMP_ZIP="/tmp/cmdline.zip"
LICENSE_LOG="/var/log/accept_licenses.log"

export ANDROID_SDK_ROOT="$CACHE_ROOT"
export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/emulator:$ANDROID_SDK_ROOT/platform-tools:$PATH"

if [ ! -f "$MARKER" ]; then
  echo "Preparing Android SDK cache at $CACHE_ROOT"
  mkdir -p "$ANDROID_SDK_ROOT"
  chmod -R u+rx "$ANDROID_SDK_ROOT" || true

  echo "Downloading command-line tools..."
  curl --fail --location --retry 3 --retry-delay 5 \
       "$CMDLINE_TOOLS_URL" -o "$TMP_ZIP"

  echo "Unpacking..."
  unzip -q "$TMP_ZIP" -d "$ANDROID_SDK_ROOT/cmdline-tools"
  rm -f "$TMP_ZIP"
  mv "$ANDROID_SDK_ROOT/cmdline-tools/cmdline-tools" "$ANDROID_SDK_ROOT/cmdline-tools/latest"
  chmod -R u+rx "$ANDROID_SDK_ROOT/cmdline-tools/latest/bin"

  SDKMANAGER="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"
  echo "Updating SDK manager..."
  "$SDKMANAGER" --update || true

  echo "Accepting licenses..."
  yes | "$SDKMANAGER" --licenses >> "$LICENSE_LOG" 2>&1 || true

  echo "Installing platform-tools, emulator, x86_64 system-image..."
  yes | "$SDKMANAGER" \
      "platform-tools" \
      "emulator" \
      "system-images;android-33;google_apis_playstore;x86_64" || true

  touch "$MARKER"
  echo "Android SDK cache prepared at $CACHE_ROOT"
else
  echo "Android SDK cache already prepared, skipping."
fi

EMULATOR_DEVICE=${EMULATOR_DEVICE:-emu-33-playstore}
if ! avdmanager list avd | grep -q "^${EMULATOR_DEVICE}$"; then
  echo "Creating AVD ${EMULATOR_DEVICE}..."
  printf "no\n" | avdmanager create avd \
    -n "${EMULATOR_DEVICE}" \
    -k "system-images;android-33;google_apis_playstore;x86_64" \
    --device "pixel_4" \
    --force
else
  echo "AVD ${EMULATOR_DEVICE} already exists, skipping."
fi

echo "Done preparing Android SDK + AVD."
