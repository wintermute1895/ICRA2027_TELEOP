#!/usr/bin/env bash
set -Eeuo pipefail

# Independent real-hand session. It does not start, stop, or read from the
# capture recorder. The controller reuses the O6 backend proven by
# hand_gesture_player.py and is the only CAN owner.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEM_PYTHON="${SYSTEM_PYTHON:-/usr/bin/python3}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
WORKSPACE_SETUP="${WORKSPACE_SETUP:-${ROOT_DIR}/ros2_ws/install/setup.bash}"
ARM="right"
MODEL="O6"
CAN_INTERFACE="auto"
ESTOP_READY=0
CONFIRM=""

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

for arg in "$@"; do
  case "$arg" in
    --arm=*) ARM="${arg#*=}" ;;
    --model=*) MODEL="${arg#*=}" ;;
    --can=*) CAN_INTERFACE="${arg#*=}" ;;
    --physical-estop-ready) ESTOP_READY=1 ;;
    --confirm=*) CONFIRM="${arg#*=}" ;;
    -h|--help)
      echo "Usage: $0 --physical-estop-ready --confirm=I_UNDERSTAND_REAL_HAND [--arm=right] [--model=O6] [--can=auto|canX]"
      exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done
[[ "$ARM" == "left" || "$ARM" == "right" ]] || { echo "arm must be left or right" >&2; exit 2; }
[[ "$MODEL" == "O6" ]] || { echo "the supplied right-hand preset config is O6; use a separate vetted config for another model" >&2; exit 2; }
[[ "$CAN_INTERFACE" == auto || "$CAN_INTERFACE" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "invalid CAN interface" >&2; exit 2; }
(( ESTOP_READY )) && [[ "$CONFIRM" == "I_UNDERSTAND_REAL_HAND" ]] || {
  echo "real hand control requires --physical-estop-ready and --confirm=I_UNDERSTAND_REAL_HAND" >&2
  exit 2
}

set +u
source "$ROS_SETUP"
source "$WORKSPACE_SETUP"
set -u
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
  LINKERTA_SAMPLE="$(timeout 5s ros2 topic echo --once --qos-durability transient_local /linkerta/can_interface 2>/dev/null || true)"
  LINKERTA_CAN="$(parse_ros_string_data <<<"$LINKERTA_SAMPLE" || true)"
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
fi
ip link show "$CAN_INTERFACE" >/dev/null 2>&1 || { echo "CAN interface not found: $CAN_INTERFACE" >&2; exit 2; }
ip link show "$CAN_INTERFACE" | grep -q 'state UP' || { echo "CAN interface is not UP: $CAN_INTERFACE" >&2; exit 2; }
if ros2 node list 2>/dev/null | grep -Eq '/(hand_adapter|hand_preset_controller|linker_hand_sdk_(left|right))$'; then
  echo "an existing hand controller/adapter/SDK node is already running; refusing a second CAN owner" >&2
  exit 2
fi

LOG_DIR="${ROS_LOG_DIR:-/tmp/teleop_hand_control_logs}"
mkdir -p "$LOG_DIR"
export ROS_LOG_DIR="$LOG_DIR"
exec "$SYSTEM_PYTHON" "$ROOT_DIR/tools/hand_preset_controller.py" \
  --config "$ROOT_DIR/config/hand_presets.json" --arm "$ARM" \
  --backend direct-o6 --can "$CAN_INTERFACE" --execute \
  --physical-estop-ready --confirm EXECUTE_HAND_PRESET_WITH_ESTOP_READY
