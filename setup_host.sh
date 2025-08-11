#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# setup_host.sh - เตรียม Ubuntu host สำหรับรัน PlayFlow (Docker, Docker Compose, scrcpy)
# Usage:
#   chmod +x setup_host.sh
#   ./setup_host.sh
# -----------------------------------------------------------------------------

# ตรวจสอบว่าเป็น Ubuntu
if [[ "$(lsb_release -si)" != "Ubuntu" ]]; then
  echo "Error: This script supports Ubuntu only."
  exit 1
fi

echo "--- Updating APT packages ---"
sudo apt-get update -y

echo "--- Installing base dependencies ---"
sudo apt-get install -y \
  apt-transport-https \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  git

# ---------------- Docker / Compose ----------------
echo "--- Adding Docker repository ---"
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
https://download.docker.com/linux/ubuntu \
$(lsb_release -cs) stable" | \
sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "--- Installing Docker Engine ---"
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

echo "--- Installing Docker Compose plugin ---"
sudo apt-get install -y docker-compose-plugin

echo "--- Docker and Docker Compose versions ---"
docker --version
docker compose version

echo "--- Adding user '$USER' to docker group ---"
sudo usermod -aG docker "$USER"

# ---------------- scrcpy / adb ----------------
# เส้นทางที่ "น่าจะ" มี scrcpy-server.jar
LOCAL_CANDIDATES=(
  "${SCRCPY_SERVER_JAR:-}"
  "/usr/local/share/scrcpy/scrcpy-server.jar"
  "/usr/share/scrcpy/scrcpy-server.jar"
  "/snap/scrcpy/current/usr/share/scrcpy/scrcpy-server.jar"
)

find_scrcpy_server() {
  for p in "${LOCAL_CANDIDATES[@]}"; do
    if [[ -n "$p" && -f "$p" ]]; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

install_scrcpy_via_apt() {
  echo "--- Installing scrcpy + adb via APT ---"
  # scrcpy จะพา server.jar มาด้วยใน /usr/share/scrcpy/
  sudo apt-get install -y scrcpy adb || return 1
}

install_scrcpy_via_snap() {
  echo "--- Installing scrcpy via Snap ---"
  # ถ้าเครื่องยังไม่มี snapd
  if ! command -v snap >/dev/null 2>&1; then
    sudo apt-get install -y snapd
  fi
  sudo snap install scrcpy || return 1
  # adb ติดตั้งจาก apt
  if ! command -v adb >/dev/null 2>&1; then
    sudo apt-get install -y adb
  fi
}

# ดาวน์โหลด server.jar ให้ตรงกับเวอร์ชัน scrcpy (ถ้ามี scrcpy อยู่แล้ว)
# จะวางไว้ที่ /usr/local/share/scrcpy/scrcpy-server.jar
download_server_jar_for_installed_scrcpy() {
  if ! command -v scrcpy >/dev/null 2>&1; then
    echo "scrcpy not installed; skip download."
    return 1
  fi

  # ดึงเวอร์ชัน scrcpy
  local ver
  ver="$(scrcpy -v | head -n1 | awk '{print $2}' || true)"
  if [[ -z "${ver:-}" ]]; then
    echo "Cannot detect scrcpy version; skip targeted download."
    return 1
  fi

  # URL release ตาม tag vX.Y (โครงโดยทั่วไปของ Genymobile/scrcpy)
  local url="https://github.com/Genymobile/scrcpy/releases/download/v${ver}/scrcpy-server-v${ver}"
  echo "--- Downloading scrcpy-server.jar (v${ver}) ---"
  sudo mkdir -p /usr/local/share/scrcpy
  # บาง release ใช้ชื่อไฟล์โดยไม่มี .jar ต่อท้าย ให้บันทึกเป็น .jar เอง
  if ! curl -fL "$url" -o /tmp/scrcpy-server.jar; then
    # สำรองอีกชื่อที่บางครั้งใช้
    url="https://github.com/Genymobile/scrcpy/releases/download/v${ver}/scrcpy-server.jar"
    curl -fL "$url" -o /tmp/scrcpy-server.jar
  fi
  sudo install -m 0644 /tmp/scrcpy-server.jar /usr/local/share/scrcpy/scrcpy-server.jar
  rm -f /tmp/scrcpy-server.jar
}

ensure_scrcpy_server() {
  echo "--- Ensuring scrcpy-server.jar is available on host ---"

  if server="$(find_scrcpy_server)"; then
    echo "Found scrcpy-server.jar at: $server"
  else
    echo "scrcpy-server.jar not found. Trying to install scrcpy..."
    if ! install_scrcpy_via_apt; then
      echo "APT install failed or unavailable; trying Snap..."
      install_scrcpy_via_snap || true
    fi

    if server="$(find_scrcpy_server)"; then
      echo "Found after install: $server"
    else
      echo "Trying to download server.jar matching installed scrcpy..."
      download_server_jar_for_installed_scrcpy || true
      if server="$(find_scrcpy_server)"; then
        echo "Downloaded: $server"
      else
        echo "ERROR: Unable to obtain scrcpy-server.jar"
        return 1
      fi
    fi
  fi

  # ตั้งค่า ENV ถาวรให้ระบบรู้ตำแหน่งไฟล์
  # (ใช้ /usr/local/share/scrcpy/scrcpy-server.jar เป็นค่าเริ่มต้นถ้าวางไว้ตรงนั้น)
  if [[ "$server" != "${SCRCPY_SERVER_JAR:-}" ]]; then
    echo "--- Setting SCRCPY_SERVER_JAR env ---"
    # เขียนลง /etc/environment (สำหรับทั้งระบบ)
    if grep -q '^SCRCPY_SERVER_JAR=' /etc/environment 2>/dev/null; then
      sudo sed -i "s|^SCRCPY_SERVER_JAR=.*|SCRCPY_SERVER_JAR=\"$server\"|g" /etc/environment
    else
      echo "SCRCPY_SERVER_JAR=\"$server\"" | sudo tee -a /etc/environment >/dev/null
    fi
    # export ให้ shell ปัจจุบันด้วย
    export SCRCPY_SERVER_JAR="$server"
  fi
}

# เรียกใช้งานส่วน scrcpy
ensure_scrcpy_server

cat <<'EOF'

Setup complete!
- Docker/Compose installed.
- scrcpy-server.jar is available on the host.
If you just added yourself to the docker group, please logout/login or run:
  newgrp docker

EOF
