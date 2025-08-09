#!/usr/bin/env bash
set -euo pipefail

NETWORK=${NETWORK:-macvlan88}

# Check docker
if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "docker daemon not running or not accessible" >&2
  exit 1
fi

CURL_OK=1
NC_OK=1
if ! command -v curl >/dev/null 2>&1; then
  echo "Warning: curl not found. Install with: apt-get install -y curl" >&2
  CURL_OK=0
fi
if ! command -v nc >/dev/null 2>&1; then
  echo "Warning: nc not found. Install with: apt-get install -y netcat-openbsd" >&2
  NC_OK=0
fi

# Colors
if [ -t 1 ]; then
  RED='\033[31m'
  GREEN='\033[32m'
  YELLOW='\033[33m'
  RESET='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; RESET=''
fi

ip_of() {
  docker inspect -f "{{range \$k,\$v := .NetworkSettings.Networks}}{{if eq \$k \"$NETWORK\"}}{{\$v.IPAddress}}{{end}}{{end}}" "$1" 2>/dev/null
}

probe_http() {
  local ip=$1 port=$2
  if [ "$CURL_OK" -eq 0 ]; then
    echo "UNKNOWN"
    return 1
  fi
  if curl -sSfI "http://$ip:$port" >/dev/null 2>&1; then
    echo "UP"
  else
    echo "DOWN"
  fi
}

probe_tcp() {
  local ip=$1 port=$2
  if [ "$NC_OK" -eq 0 ]; then
    echo "UNKNOWN"
    return 1
  fi
  if nc -z -w 1 "$ip" "$port" >/dev/null 2>&1; then
    echo "UP"
  else
    echo "DOWN"
  fi
}

colorize() {
  case "$1" in
    UP) echo "${GREEN}$1${RESET}";;
    DOWN) echo "${RED}$1${RESET}";;
    NO\ IP*) echo "${YELLOW}$1${RESET}";;
    UNKNOWN) echo "${YELLOW}$1${RESET}";;
    *) echo "$1";;
  esac
}

printf "PlayFlow Endpoints (network: %s)\n" "$NETWORK"
printf -- "--------------------------------------------------------------------------------\n"
format="%-13s %-15s %-9s %-5s %-5s %-12s %-7s %s\n"
printf "$format" "Container" "IP Address" "Service" "Port" "Proto" "Access" "Status" "URL/How"
printf -- "--------------------------------------------------------------------------------\n"

notes=()

# pf_emulator
container=pf_emulator
ip=$(ip_of "$container")
if [ -z "$ip" ]; then
  status="NO IP (DHCP?)"
  printf "$format" "$container" "" "noVNC" "6080" "TCP" "Browser" "$(colorize "$status")" "-"
  printf "$format" "$container" "" "VNC" "5900" "TCP" "VNC client" "$(colorize "$status")" "-"
  printf "$format" "$container" "" "ADB" "5037" "TCP" "LAN/Containers" "$(colorize "$status")" "-"
else
  status=$(probe_http "$ip" 6080)
  printf "$format" "$container" "$ip" "noVNC" "6080" "TCP" "Browser" "$(colorize "$status")" "http://$ip:6080"

  status=$(probe_tcp "$ip" 5900)
  if [ "$status" != "UP" ]; then
    notes+=("เช็ค VNC password ไฟล์ /root/.vnc/passwd")
  fi
  printf "$format" "$container" "$ip" "VNC" "5900" "TCP" "VNC client" "$(colorize "$status")" "vnc://$ip:5900"

  status=$(probe_tcp "$ip" 5037)
  if [ "$status" != "UP" ]; then
    notes+=("ADB server อาจ bind แค่ 127.0.0.1; ตรวจ ADB_SERVER_SOCKET=tcp:5037 ใน start.sh")
  fi
  printf "$format" "$container" "$ip" "ADB" "5037" "TCP" "LAN/Containers" "$(colorize "$status")" "adb connect $ip:5037"
fi

# pf_droidflow
container=pf_droidflow
ip=$(ip_of "$container")
if [ -z "$ip" ]; then
  status="NO IP (DHCP?)"
  printf "$format" "$container" "" "Flask UI" "5000" "TCP" "Browser" "$(colorize "$status")" "-"
else
  status=$(probe_http "$ip" 5000)
  printf "$format" "$container" "$ip" "Flask UI" "5000" "TCP" "Browser" "$(colorize "$status")" "http://$ip:5000/"
fi

printf -- "--------------------------------------------------------------------------------\n"
notes+=("macvlan: host may not reach containers directly; use another LAN device.")
if [ ${#notes[@]} -gt 0 ]; then
  printf "Notes:\n"
  for n in "${notes[@]}"; do
    printf "- %s\n" "$n"
  done
fi
