#!/usr/bin/env bash
set -Eeuo pipefail

# Independent real-hand session. It does not start, stop, or read from the
# capture recorder. The controller reuses the O6 backend proven by
# hand_gesture_player.py and is the only CAN owner.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The direct O6 backend needs the Python CAN dependency, which is installed in
# the active teleop environment on this machine.  Fall back to the system ROS
# interpreter when no Conda environment is active.
if [[ -n "${SYSTEM_PYTHON:-}" ]]; then
  SYSTEM_PYTHON="$SYSTEM_PYTHON"
elif [[ -n "${CONDA_PREFIX:-}" && -x "$CONDA_PREFIX/bin/python" ]]; then
  SYSTEM_PYTHON="$CONDA_PREFIX/bin/python"
else
  SYSTEM_PYTHON="/usr/bin/python3"
fi
# Prefer an explicitly supplied setup file; otherwise select an installed ROS
# distribution.  This host uses Humble, while the old default assumed Jazzy.
if [[ -n "${ROS_SETUP:-}" ]]; then
  ROS_SETUP="$ROS_SETUP"
else
  ROS_SETUP=""
  for distro in "${ROS_DISTRO:-}" humble jazzy; do
    [[ -n "$distro" && -f "/opt/ros/$distro/setup.bash" ]] || continue
    ROS_SETUP="/opt/ros/$distro/setup.bash"
    break
  done
fi
WORKSPACE_SETUP="${WORKSPACE_SETUP:-${ROOT_DIR}/ros2_ws/install/setup.bash}"
CONFIG_FILE="${HAND_CONTROL_CONFIG:-$ROOT_DIR/config/hands/o6_control.env}"
ARM="right"
MODEL="O6"
CAN_INTERFACE="auto"
PRESET_CONFIG="$ROOT_DIR/config/hand_presets.json"
LOG_DIR="${ROS_LOG_DIR:-/tmp/teleop_hand_control_logs}"
ESTOP_READY=0
CONFIRM=""

ARGS=("$@")
for ((index = 0; index < ${#ARGS[@]}; index++)); do
  case "${ARGS[index]}" in
    --config=*) CONFIG_FILE="${ARGS[index]#*=}" ;;
    --config) ((index += 1)); CONFIG_FILE="${ARGS[index]:-}" ;;
  esac
done
if [[ "$CONFIG_FILE" != /* ]]; then
  CONFIG_FILE="$ROOT_DIR/$CONFIG_FILE"
fi
[[ -f "$CONFIG_FILE" ]] || { echo "hand control config not found: $CONFIG_FILE" >&2; exit 2; }
# shellcheck disable=SC1090
source "$CONFIG_FILE"
[[ -n "${HAND_ARM:-}" ]] && ARM="$HAND_ARM"
[[ -n "${HAND_MODEL:-}" ]] && MODEL="$HAND_MODEL"
[[ -n "${HAND_CAN_INTERFACE:-}" ]] && CAN_INTERFACE="$HAND_CAN_INTERFACE"
if [[ -n "${HAND_PRESET_CONFIG:-}" ]]; then
  PRESET_CONFIG="$HAND_PRESET_CONFIG"
  [[ "$PRESET_CONFIG" == /* ]] || PRESET_CONFIG="$ROOT_DIR/$PRESET_CONFIG"
fi
[[ -n "${HAND_LOG_DIR:-}" ]] && LOG_DIR="$HAND_LOG_DIR"

parse_ros_string_data() {
  local line value first last
  while IFS= read -r line; do
    [[ "$line" == data:* ]] || continue
    value="${line#data:}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if (( ${#value} >= 2 )); then
      first="${value:0:1}"
      last="${value: -1}"
      if [[ "$first" == "$last" ]] && { [[ "$first" == "'" ]] || [[ "$first" == '"' ]]; }; then
        value="${value:1:${#value}-2}"
      fi
    fi
    if [[ "$value" =~ ^[A-Za-z0-9._-]+$ ]]; then
      printf '%s\n' "$value"
      return 0
    fi
  done
  return 1
}

for ((arg_index = 0; arg_index < ${#ARGS[@]}; arg_index++)); do
  arg="${ARGS[arg_index]}"
  case "$arg" in
    --config=*) ;;
    --config) ((arg_index += 1)) ;;
    --arm=*) ARM="${arg#*=}" ;;
    --model=*) MODEL="${arg#*=}" ;;
    --can=*) CAN_INTERFACE="${arg#*=}" ;;
    --physical-estop-ready) ESTOP_READY=1 ;;
    --confirm=*) CONFIRM="${arg#*=}" ;;
    -h|--help)
      echo "Usage: $0 --physical-estop-ready --confirm=I_UNDERSTAND_REAL_HAND [--config=PATH] [--arm=right] [--model=O6] [--can=auto|canX]"
      exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done
[[ "$ARM" == "left" || "$ARM" == "right" ]] || { echo "arm must be left or right" >&2; exit 2; }
[[ "$MODEL" == "O6" ]] || { echo "the supplied right-hand preset config is O6; use a separate vetted config for another model" >&2; exit 2; }
[[ "$CAN_INTERFACE" == auto || "$CAN_INTERFACE" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "invalid CAN interface" >&2; exit 2; }
[[ -f "$PRESET_CONFIG" ]] || { echo "hand preset config not found: $PRESET_CONFIG" >&2; exit 2; }
[[ -n "$ROS_SETUP" && -f "$ROS_SETUP" ]] || { echo "ROS2 setup file not found; set ROS_SETUP=/opt/ros/<distro>/setup.bash" >&2; exit 2; }
(( ESTOP_READY )) && [[ "$CONFIRM" == "I_UNDERSTAND_REAL_HAND" ]] || {
  echo "real hand control requires --physical-estop-ready and --confirm=I_UNDERSTAND_REAL_HAND" >&2
  exit 2
}

set +u
source "$ROS_SETUP"
source "$WORKSPACE_SETUP"
set -u
LINKERTA_SAMPLE="$(timeout 5s ros2 topic echo --once /linkerta/can_interface 2>/dev/null || true)"
LINKERTA_CAN="$(parse_ros_string_data <<<"$LINKERTA_SAMPLE" || true)"
if [[ "$CAN_INTERFACE" == auto ]]; then
  CANDIDATES=()
  for iface_path in /sys/class/net/can*; do
    [[ -e "$iface_path" ]] || continue
    iface="${iface_path##*/}"
    [[ "$(cat "$iface_path/operstate" 2>/dev/null || true)" == up ]] && CANDIDATES+=("$iface")
  done
  if (( ${#CANDIDATES[@]} == 0 )); then
    echo "CAN auto-detection found no UP SocketCAN interfaces" >&2
    exit 2
  fi
  if [[ -z "$LINKERTA_CAN" ]]; then
    echo "LinkerTA CAN assignment is unavailable on /linkerta/can_interface." >&2
    echo "Start the capture session first, then start this independent hand controller." >&2
    echo "No hand SDK was started and no CAN probe was sent." >&2
    exit 2
  fi
  REMAINING=()
  for candidate in "${CANDIDATES[@]}"; do
    [[ "$candidate" == "$LINKERTA_CAN" ]] || REMAINING+=("$candidate")
  done
  if (( ${#REMAINING[@]} != 1 )); then
    echo "Cannot select a unique hand CAN after excluding LinkerTA=$LINKERTA_CAN; remaining: ${REMAINING[*]:-none}" >&2
    exit 2
  fi
  CAN_INTERFACE="${REMAINING[0]}"
elif [[ -n "$LINKERTA_CAN" && "$CAN_INTERFACE" == "$LINKERTA_CAN" ]]; then
  echo "refusing hand control on LinkerTA's assigned CAN interface: $CAN_INTERFACE" >&2
  echo "choose the verified hand interface from the separate CAN bus" >&2
  exit 2
fi
ip link show "$CAN_INTERFACE" >/dev/null 2>&1 || { echo "CAN interface not found: $CAN_INTERFACE" >&2; exit 2; }
ip link show "$CAN_INTERFACE" | grep -q 'state UP' || { echo "CAN interface is not UP: $CAN_INTERFACE" >&2; exit 2; }
if ros2 node list 2>/dev/null | grep -Eq '/(hand_adapter|hand_preset_controller|linker_hand_sdk_(left|right))$'; then
  echo "an existing hand controller/adapter/SDK node is already running; refusing a second CAN owner" >&2
  exit 2
fi

mkdir -p "$LOG_DIR"
export ROS_LOG_DIR="$LOG_DIR"
exec "$SYSTEM_PYTHON" "$ROOT_DIR/tools/hand_preset_controller.py" \
  --config "$PRESET_CONFIG" --arm "$ARM" \
  --backend direct-o6 --can "$CAN_INTERFACE" --execute \
  --physical-estop-ready --confirm EXECUTE_HAND_PRESET_WITH_ESTOP_READY
