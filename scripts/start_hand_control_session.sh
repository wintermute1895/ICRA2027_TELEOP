#!/usr/bin/env bash
set -Eeuo pipefail

# Independent real-hand session. It does not start, stop, or read from the
# capture recorder. The official SDK owns CAN; the keyboard controller only
# publishes the existing ROS adapter topic.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEM_PYTHON="${SYSTEM_PYTHON:-/usr/bin/python3}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
WORKSPACE_SETUP="${WORKSPACE_SETUP:-${ROOT_DIR}/ros2_ws/install/setup.bash}"
ARM="right"
MODEL="O6"
CAN_INTERFACE="auto"
ESTOP_READY=0
CONFIRM=""

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
fi
if [[ "$CAN_INTERFACE" != auto ]]; then
  ip link show "$CAN_INTERFACE" >/dev/null 2>&1 || { echo "CAN interface not found: $CAN_INTERFACE" >&2; exit 2; }
  ip link show "$CAN_INTERFACE" | grep -q 'state UP' || { echo "CAN interface is not UP: $CAN_INTERFACE" >&2; exit 2; }
else
  CANDIDATES=("${CANDIDATES[@]}")
fi
if ros2 node list 2>/dev/null | grep -Eq '/(hand_adapter|linker_hand_sdk_(left|right))$'; then
  echo "an existing hand adapter/SDK node is already running; refusing a second CAN owner" >&2
  exit 2
fi

LOG_DIR="${ROS_LOG_DIR:-/tmp/teleop_hand_control_logs}"
mkdir -p "$LOG_DIR"
SDK_MODEL="$MODEL"
[[ "$MODEL" == "L20Lite" ]] && SDK_MODEL="L10"
STATE_TOPIC="/robot1/${ARM}_hand/joint_states"
launch_backend() {
  local can_interface="$1" armed="$2" allow_commands="$3" launch_log="$4"
  if [[ "$ARM" == "right" ]]; then
    ros2 launch hand_adapter hand_interface.launch.py \
      armed:="$armed" launch_right_sdk:=true launch_left_sdk:=false \
      right_model:="$MODEL" right_sdk_model:="$SDK_MODEL" right_can:="$can_interface" \
      initialize_pose:=false allow_sdk_commands:="$allow_commands" >"$launch_log" 2>&1 &
  else
    ros2 launch hand_adapter hand_interface.launch.py \
      armed:="$armed" launch_left_sdk:=true launch_right_sdk:=false \
      left_model:="$MODEL" left_sdk_model:="$SDK_MODEL" left_can:="$can_interface" \
      initialize_pose:=false allow_sdk_commands:="$allow_commands" >"$launch_log" 2>&1 &
  fi
  echo $!
}

stop_backend() {
  local pid="$1"
  kill -INT "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.1
  done
  kill -TERM "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
}

valid_state_sample() {
  "$SYSTEM_PYTHON" -c '
import re, sys
text = sys.stdin.read()
match = re.search(r"(?:^|\n)position:\s*(.*?)(?:\n(?:velocity|effort|---):|\Z)", text, re.S)
values = [] if match is None else [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", match.group(1))]
raise SystemExit(0 if values and any(value >= 0.0 for value in values) else 1)
'
}

if [[ "$CAN_INTERFACE" == auto ]]; then
  RESPONDING=()
  for candidate in "${CANDIDATES[@]}"; do
    probe_log="$LOG_DIR/hand_probe_${candidate}_$(date +%Y%m%dT%H%M%S).log"
    probe_pid="$(launch_backend "$candidate" false false "$probe_log")"
    sample="$(timeout 8s ros2 topic echo --once "$STATE_TOPIC" 2>/dev/null || true)"
    if valid_state_sample <<<"$sample"; then
      RESPONDING+=("$candidate")
    fi
    stop_backend "$probe_pid"
    sleep 0.5
  done
  if (( ${#RESPONDING[@]} != 1 )); then
    echo "CAN auto-detection could not identify exactly one hand interface; responding candidates: ${RESPONDING[*]:-none}" >&2
    echo "Probe logs: $LOG_DIR/hand_probe_*.log" >&2
    echo "Pass --can=<interface> only after checking the wiring." >&2
    exit 2
  fi
  CAN_INTERFACE="${RESPONDING[0]}"
fi

LAUNCH_LOG="$LOG_DIR/hand_control_$(date +%Y%m%dT%H%M%S).log"
LAUNCH_PID="$(launch_backend "$CAN_INTERFACE" true true "$LAUNCH_LOG")"
cleanup() { stop_backend "$LAUNCH_PID"; }
trap cleanup EXIT INT TERM
for _ in $(seq 1 60); do
  kill -0 "$LAUNCH_PID" 2>/dev/null || { echo "hand SDK exited; inspect $LAUNCH_LOG" >&2; exit 3; }
  if timeout 1s ros2 topic echo --once "$STATE_TOPIC" >/dev/null 2>&1; then
    echo "[HAND] state ready: $STATE_TOPIC (can=$CAN_INTERFACE, model=$MODEL)"
    "$SYSTEM_PYTHON" "$ROOT_DIR/tools/hand_preset_controller.py" \
      --config "$ROOT_DIR/config/hand_presets.json" --arm "$ARM" \
      --execute --physical-estop-ready \
      --confirm EXECUTE_HAND_PRESET_WITH_ESTOP_READY
    exit $?
  fi
  sleep 0.25
done
echo "no hand state received; inspect $LAUNCH_LOG" >&2
exit 3
