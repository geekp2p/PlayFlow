ip_of() {
  local c="$1"
  local ip

  # 1) ลองจาก docker inspect ก่อน (จะเวิร์คเฉพาะกรณีมี IPAddress ใน network นั้นจริง ๆ)
  ip=$(docker inspect -f "{{range \$k,\$v := .NetworkSettings.Networks}}{{if eq \$k \"$NETWORK\"}}{{\$v.IPAddress}}{{end}}{{end}}" "$c" 2>/dev/null)
  if [ -n "$ip" ]; then
    echo "$ip"
    return 0
  fi

  # 2) macvlan + DHCP: ดูจากภายใน container (eth0)
  ip=$(timeout 2s docker exec "$c" sh -c "ip -4 addr show dev eth0 2>/dev/null | awk '/inet /{print \$2}' | cut -d/ -f1 | head -n1" 2>/dev/null || true)
  if [ -n "$ip" ]; then
    echo "$ip"
    return 0
  fi

  # 3) fallback (busybox/alpine)
  ip=$(timeout 2s docker exec "$c" sh -c "hostname -I 2>/dev/null | awk '{print \$1}'" 2>/dev/null || true)
  [ -n "$ip" ] && echo "$ip"
}
