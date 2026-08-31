#!/usr/bin/env bash
# Bring every currently present SocketCAN canN interface up at one bitrate.
set -euo pipefail

BITRATE="1000000"
CONFIRM=""

usage() {
  cat >&2 <<'EOF'
Usage: sudo bash scripts/enable_all_can.sh [--bitrate 1000000] \
  --confirm ENABLE_ALL_CAN_INTERFACES

Only existing Linux interfaces named canN are changed. This does not start a
vendor SDK, connect a hand, or transmit a CAN frame.
EOF
}

while (($#)); do
  case "$1" in
    --bitrate) BITRATE="${2:-}"; shift 2 ;;
    --confirm) CONFIRM="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ "${EUID}" -eq 0 ]] || { echo "Run with sudo." >&2; exit 2; }
[[ "$BITRATE" =~ ^[1-9][0-9]*$ ]] || { echo "--bitrate must be a positive integer" >&2; exit 2; }
[[ "$CONFIRM" == "ENABLE_ALL_CAN_INTERFACES" ]] || {
  echo "explicit --confirm ENABLE_ALL_CAN_INTERFACES is required" >&2
  exit 2
}

mapfile -t interfaces < <(compgen -G '/sys/class/net/can*' | xargs -r -n1 basename | sort -V)
((${#interfaces[@]})) || { echo "No SocketCAN canN interfaces are present." >&2; exit 1; }

for interface in "${interfaces[@]}"; do
  echo "[ACTION] setting $interface UP at $BITRATE bit/s"
  ip link set "$interface" down 2>/dev/null || true
  ip link set "$interface" up type can bitrate "$BITRATE"
  ip -details link show "$interface"
done
