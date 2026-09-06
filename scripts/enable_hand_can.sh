#!/usr/bin/env bash
# Explicit SocketCAN interface setup for the official LinkerHand SDK.
set -Eeuo pipefail

INTERFACE=""
BITRATE="1000000"
CONFIRM=""

usage() {
  cat >&2 <<'EOF'
Usage: bash scripts/enable_hand_can.sh --interface can0|can1 [--bitrate 1000000] \
  --confirm ENABLE_HAND_CAN_INTERFACE

This changes only the Linux SocketCAN interface state. It does not start the
SDK, connect a hand, or transmit a hand command. sudo permission is required.
EOF
}

while (($#)); do
  case "$1" in
    --interface) INTERFACE="${2:-}"; shift 2 ;;
    --bitrate) BITRATE="${2:-}"; shift 2 ;;
    --confirm) CONFIRM="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ "$INTERFACE" =~ ^can[0-9]+$ ]] || { echo "--interface must be a SocketCAN name such as can0" >&2; exit 2; }
[[ "$BITRATE" =~ ^[1-9][0-9]*$ ]] || { echo "--bitrate must be a positive integer" >&2; exit 2; }
[[ "$CONFIRM" == "ENABLE_HAND_CAN_INTERFACE" ]] || { echo "explicit --confirm ENABLE_HAND_CAN_INTERFACE is required" >&2; exit 2; }
command -v ip >/dev/null || { echo "iproute2 is not installed" >&2; exit 2; }
[[ -d "/sys/class/net/$INTERFACE" ]] || { echo "SocketCAN interface does not exist: $INTERFACE" >&2; exit 2; }

if ip -details link show "$INTERFACE" | grep -q "state UP"; then
  echo "[PASS] $INTERFACE is already UP"
  ip -details link show "$INTERFACE"
  exit 0
fi

echo "[ACTION] setting $INTERFACE UP at ${BITRATE} bit/s"
sudo ip link set "$INTERFACE" up type can bitrate "$BITRATE"
ip -details link show "$INTERFACE"
