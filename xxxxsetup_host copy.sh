#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# setup_host.sh - เตรียม Ubuntu host สำหรับรัน PlayFlow (Docker, Docker Compose)
# Usage: 
#   chmod +x setup_host.sh
#   ./setup_host.sh
# -----------------------------------------------------------------------------

# ตรวจสอบว่ารันบน Ubuntu หรือไม่
if [[ "$(lsb_release -si)" != "Ubuntu" ]]; then
  echo "Error: This script supports Ubuntu only."
  exit 1
fi

# อัพเดตแพ็กเกจ
echo "--- Updating APT packages ---"
sudo apt-get update -y

# ติดตั้ง dependencies เบื้องต้น
echo "--- Installing base dependencies ---"
sudo apt-get install -y \
  apt-transport-https \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  git

# เพิ่ม Docker GPG key และ repository
echo "--- Adding Docker repository ---"
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# ติดตั้ง Docker Engine
echo "--- Installing Docker Engine ---"
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# ติดตั้ง Docker Compose (plugin)
echo "--- Installing Docker Compose plugin ---"
sudo apt-get install -y docker-compose-plugin

# ตรวจสอบเวอร์ชัน
echo "--- Docker and Docker Compose versions ---"
docker --version
docker compose version

# เพิ่ม user ปัจจุบันลง Docker group
echo "--- Adding user '$USER' to docker group ---"
sudo usermod -aG docker "$USER"

echo "
Setup complete! Please logout/login หรือรัน:
  newgrp docker
เพื่อให้กลุ่ม docker มีผล
"
