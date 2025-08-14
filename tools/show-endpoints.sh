#!/usr/bin/env bash
set -euo pipefail

# Check docker
if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found" >&2
  exit 0
fi
if ! docker info >/dev/null 2>&1; then
  echo "docker daemon not running or not accessible" >&2
  exit 0
fi

# NETWORK=${NETWORK:-macvlan88}
NETWORK=${NETWORK:-backend}

# Determine if the requested network exists. Docker Compose often prefixes
# network names with the project name (e.g. playflow_macvlan88). If the user
# didn't explicitly set NETWORK, try to auto-detect such a prefixed name.
network_exists=true
if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
  alt=$(docker network ls --format '{{.Name}}' | grep "_${NETWORK}$" | head -n1 || true)
  if [ -n "$alt" ]; then
    NETWORK="$alt"
  else
    network_exists=false
  fi
fi

# Check docker
# if ! command -v docker >/dev/null 2>&1; then
#   echo "docker command not found" >&2
#   exit 1
# fi
# if ! docker info >/dev/null 2>&1; then
#   echo "docker daemon not running or not accessible" >&2
#   exit 1
# fi

# Colors
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  RED='\033[31m'
  GREEN='\033[32m'
  YELLOW='\033[33m'
  RESET='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; RESET=''
fi

HOST_IP=${HOST_IP:-$(hostname -I 2>/dev/null | awk '{print $1}' | tr -d '\n')}
[ -z "$HOST_IP" ] && HOST_IP=127.0.0.1

ip_of() {
  local c="$1" ip sel
  ip=$(docker inspect -f "{{range \$k,\$v := .NetworkSettings.Networks}}{{if eq \$k \"$NETWORK\"}}{{\$v.IPAddress}}{{end}}{{end}}" "$c" 2>/dev/null || true)
  if [ -n "$ip" ]; then
    echo "$ip"
    return 0
  fi

  ip=$(timeout 2s docker exec "$c" sh -c "ip -4 -o addr show up scope global | awk '{print \$4}' | cut -d/ -f1" 2>/dev/null || true)
  if [ -n "$ip" ]; then
    sel=$(echo "$ip" | grep -E '^192\.168\.88\.' | head -n1)
    if [ -n "$sel" ]; then
      echo "$sel"
      return 0
    fi
    sel=$(echo "$ip" | grep -v '^172\.' | head -n1)
    if [ -n "$sel" ]; then
      echo "$sel"
      return 0
    fi
    echo "$ip" | head -n1
    return 0
  fi

  # 3) fallback (busybox/alpine)
  ip=$(timeout 2s docker exec "$c" sh -c "hostname -I 2>/dev/null" 2>/dev/null || true)
  if [ -n "$ip" ]; then
    ip=$(echo "$ip" | tr ' ' '\n' | grep -v '^172\.' | head -n1 || true)
    [ -n "$ip" ] && echo "$ip"
  fi
  return 0
}

probe_http() {
  local ip=$1 port=$2
  if [ "$network_exists" = true ] && docker run --rm --network "$NETWORK" alpine:3.19 sh -c "wget -qO- http://$ip:$port >/dev/null" 2>/dev/null; then
    echo "UP"
  else
    echo "DOWN"
  fi
}

probe_tcp() {
  local ip=$1 port=$2
  if [ "$network_exists" = true ] && docker run --rm --network "$NETWORK" alpine:3.19 sh -c "nc -z -w 1 $ip $port" 2>/dev/null; then
    echo "UP"
  else
    echo "DOWN"
  fi
}

colorize() {
  case "$1" in
    UP) printf '%b' "${GREEN}$1${RESET}";;
    DOWN) printf '%b' "${RED}$1${RESET}";;
    NO\ IP*) printf '%b' "${YELLOW}$1${RESET}";;
    UNKNOWN) printf '%b' "${YELLOW}$1${RESET}";;
    *) printf '%s' "$1";;
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
  printf "$format" "$container" "" "ADB" "-" "TCP" "Internal" "$(colorize "$status")" "docker exec pf_droidflow adb devices"
else
  status=$(probe_http "$ip" 6080)
  printf "$format" "$container" "$ip" "noVNC" "6080" "TCP" "Browser" "$(colorize "$status")" "http://$HOST_IP:6080"

  status=$(probe_tcp "$ip" 5900)
  if [ "$status" != "UP" ]; then
    notes+=("Check VNC password at /root/.vnc/passwd")
  fi
  printf "$format" "$container" "$ip" "VNC" "5900" "TCP" "VNC client" "$(colorize "$status")" "vnc://$HOST_IP:5900"

  printf "$format" "$container" "$ip" "ADB" "-" "TCP" "Internal" "$(colorize "UP")" "docker exec pf_droidflow adb devices"
  notes+=("ADB is internal; run 'docker exec pf_droidflow adb ...' or 'adb connect pf_emulator:5556' inside pf_droidflow")
fi

# pf_droidflow
container=pf_droidflow
ip=$(ip_of "$container")
if [ -z "$ip" ]; then
  status="NO IP (DHCP?)"
  printf "$format" "$container" "" "Flask UI" "5000" "TCP" "Browser" "$(colorize "$status")" "-"
else
  status=$(probe_http "$ip" 5000)
  printf "$format" "$container" "$ip" "Flask UI" "5000" "TCP" "Browser" "$(colorize "$status")" "http://$HOST_IP:5000/"
fi

printf -- "--------------------------------------------------------------------------------\n"
notes+=("macvlan: host may not reach containers directly; use another LAN device.")
# notes+=("ADB is internal; run 'docker exec pf_droidflow adb ...' for direct commands")
if [ ${#notes[@]} -gt 0 ]; then
  printf "Notes:\n"
  for n in "${notes[@]}"; do
    printf -- "- %s\n" "$n"
  done
fi
