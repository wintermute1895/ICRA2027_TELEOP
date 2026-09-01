#!/usr/bin/env bash
# One-command, tmux-based robot teleoperation capture launcher.
# Safe by default: the teleop bridge is started with armed=false.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# ROS 2 Jazzy and its Python extensions are installed against the system
# interpreter.  Keep capture tooling independent of an activated Conda shell.
SYSTEM_PYTHON="${SYSTEM_PYTHON:-/usr/bin/python3}"
[[ -x "$SYSTEM_PYTHON" ]] || { echo "[FATAL] system Python not found: $SYSTEM_PYTHON" >&2; exit 2; }
CONFIG_FILE="${CAPTURE_CONFIG:-$ROOT_DIR/config/capture_session.env}"
DATA_ROOT="${CAPTURE_DATA_ROOT:-}"
if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi
# Resolve an explicitly requested config before applying defaults.
for arg in "$@"; do
  if [[ "$arg" == --config=* ]]; then
    CONFIG_FILE="${arg#*=}"
    [[ -f "$CONFIG_FILE" ]] || { echo "[FATAL] config file not found: $CONFIG_FILE" >&2; exit 2; }
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
  fi
done
SESSION="teleop_capture"
DURATION_S="30"
EPISODES="2"
CAPTURE_MODE="timed"
REAL=0
ESTOP_READY=0
CONFIRM=""
CAMERA_SERIAL="261722075670"
CAMERA_NAMESPACE="/camera/camera"
SECOND_CAMERA_SERIAL=""
SECOND_CAMERA_NAMESPACE="/camera2/camera"
WIDTH=640
HEIGHT=480
FPS=15
PREVIEW=1
EXPERIMENT_PROFILE="$ROOT_DIR/config/experiments/precision_assembly_ab.yaml"
CONDITION_ID="unassigned"
OPERATOR_ID="anonymous"
AUDITOR_ID="auditor_01"
TASK_ID="unspecified"
EXPERIMENT_MANIFEST=""
HAND_SDK=0
LEFT_HAND_CAN="can0"
RIGHT_HAND_CAN="can1"
LEFT_TOUCH="false"
RIGHT_TOUCH="false"
ARMS="left,right"

usage() {
  cat >&2 <<'EOF'
Usage:
  start_capture_session.sh [options]

Safe default starts the real-robot driver and recorder but keeps teleop armed=false.
Options:
  --config PATH                  load session defaults (default: config/capture_session.env)
  --data-root PATH               store RunEvidence directly on an external disk
  --real                         allow armed=true (still requires both confirmations)
  --physical-estop-ready        confirm physical E-stop is reachable
  --confirm=I_UNDERSTAND_REAL_ROBOT
  --duration-s SEC               timed episode duration / metadata field (default: 30)
  --episodes N                   number of episodes; 0 keeps the recorder ready until q (default: 2)
  --manual-segments              recorder window: Enter=start, Enter=stop/save, q=end session
  --session NAME                 tmux session name (default: teleop_capture)
  --no-preview                   do not open rqt_image_view
  --camera-serial SERIAL         RealSense serial (default: 261722075670)
  --second-camera-serial SERIAL  optional second RealSense serial
  --second-camera-namespace NS   second RGB-D namespace (default: /camera2/camera)
  --experiment-profile PATH      experiment profile YAML
  --condition=ID                 legacy condition metadata; formal runs use --experiment-manifest
  --operator-id=ID               de-identified operator ID
  --auditor-id=ID                second-person keyboard auditor ID
  --task-id=ID                   task/fixture identifier
  --experiment-manifest PATH     immutable manifest from tools/resolve_experiment_manifest.py
  --hand-sdk                     start LinkerHand SDK for state/tactile recording (hands remain disarmed)
  --left-hand-can=CAN            left hand CAN interface (default: can0)
  --right-hand-can=CAN           right hand CAN interface (default: can1)
  --left-touch                   enable left tactile sensor SDK stream
  --right-touch                  enable right tactile sensor SDK stream
  --arms=left,right|right         active arm set for capture (default: left,right)
EOF
}

die() { echo "[FATAL] $*" >&2; exit 2; }
log() { echo "[teleop-capture] $*"; }

# Apply config-file defaults first; explicit CLI options below override them.
[[ "${CAPTURE_REAL:-false}" == true ]] && REAL=1
[[ -n "${CAPTURE_ARMS:-}" ]] && ARMS="$CAPTURE_ARMS"
[[ -n "${CAPTURE_EPISODES:-}" ]] && EPISODES="$CAPTURE_EPISODES"
[[ -n "${CAPTURE_CAMERA_SERIAL:-}" ]] && CAMERA_SERIAL="$CAPTURE_CAMERA_SERIAL"
[[ -n "${CAPTURE_SECOND_CAMERA_SERIAL:-}" ]] && SECOND_CAMERA_SERIAL="$CAPTURE_SECOND_CAMERA_SERIAL"
[[ -n "${CAPTURE_SECOND_CAMERA_NAMESPACE:-}" ]] && SECOND_CAMERA_NAMESPACE="$CAPTURE_SECOND_CAMERA_NAMESPACE"
[[ -n "${CAPTURE_TASK_ID:-}" ]] && TASK_ID="$CAPTURE_TASK_ID"
[[ -n "${CAPTURE_OPERATOR_ID:-}" ]] && OPERATOR_ID="$CAPTURE_OPERATOR_ID"
[[ -n "${CAPTURE_AUDITOR_ID:-}" ]] && AUDITOR_ID="$CAPTURE_AUDITOR_ID"
[[ "${CAPTURE_MANUAL_SEGMENTS:-false}" == true ]] && CAPTURE_MODE="manual"
[[ "${CAPTURE_NO_PREVIEW:-false}" == true ]] && PREVIEW=0
[[ -n "${CAPTURE_DATA_ROOT:-}" ]] && DATA_ROOT="$CAPTURE_DATA_ROOT"

for arg in "$@"; do
  case "$arg" in
    --config=*) CONFIG_FILE="${arg#*=}"; [[ -f "$CONFIG_FILE" ]] || die "config file not found: $CONFIG_FILE"; source "$CONFIG_FILE" ;;
    --data-root=*) DATA_ROOT="${arg#*=}" ;;
    --real) REAL=1 ;;
    --physical-estop-ready) ESTOP_READY=1 ;;
    --confirm=*) CONFIRM="${arg#*=}" ;;
    --duration-s=*) DURATION_S="${arg#*=}" ;;
    --episodes=*) EPISODES="${arg#*=}" ;;
    --manual-segments) CAPTURE_MODE="manual" ;;
    --session=*) SESSION="${arg#*=}" ;;
    --no-preview) PREVIEW=0 ;;
    --camera-serial=*) CAMERA_SERIAL="${arg#*=}" ;;
    --second-camera-serial=*) SECOND_CAMERA_SERIAL="${arg#*=}" ;;
    --second-camera-namespace=*) SECOND_CAMERA_NAMESPACE="${arg#*=}" ;;
    --experiment-profile=*) EXPERIMENT_PROFILE="${arg#*=}" ;;
    --condition=*) CONDITION_ID="${arg#*=}" ;;
    --operator-id=*) OPERATOR_ID="${arg#*=}" ;;
    --auditor-id=*) AUDITOR_ID="${arg#*=}" ;;
    --task-id=*) TASK_ID="${arg#*=}" ;;
    --experiment-manifest=*) EXPERIMENT_MANIFEST="${arg#*=}" ;;
    --hand-sdk) HAND_SDK=1 ;;
    --left-hand-can=*) LEFT_HAND_CAN="${arg#*=}" ;;
    --right-hand-can=*) RIGHT_HAND_CAN="${arg#*=}" ;;
    --left-touch) LEFT_TOUCH="true" ;;
    --right-touch) RIGHT_TOUCH="true" ;;
    --arms=*) ARMS="${arg#*=}" ;;
    -h|--help) usage; exit 0 ;;
    *) usage; die "unknown option: $arg" ;;
  esac
done

[[ "$DURATION_S" =~ ^[1-9][0-9]*$ ]] || die "--duration-s must be a positive integer"
[[ "$EPISODES" =~ ^[0-9]+$ ]] || die "--episodes must be a non-negative integer"
(( ${#SESSION} <= 40 )) || die "tmux session name is too long"
[[ -f "$EXPERIMENT_PROFILE" ]] || die "experiment profile not found: $EXPERIMENT_PROFILE"
[[ "$CONDITION_ID" =~ ^[A-Za-z0-9._-]+$ ]] || die "--condition contains unsupported characters"
[[ "$OPERATOR_ID" =~ ^[A-Za-z0-9._-]+$ ]] || die "--operator-id contains unsupported characters"
[[ "$AUDITOR_ID" =~ ^[A-Za-z0-9._-]+$ ]] || die "--auditor-id contains unsupported characters"
[[ "$TASK_ID" =~ ^[A-Za-z0-9._-]+$ ]] || die "--task-id contains unsupported characters"
[[ "$SECOND_CAMERA_NAMESPACE" =~ ^/[A-Za-z0-9_/-]+$ ]] || die "--second-camera-namespace contains unsupported characters"
[[ "$LEFT_HAND_CAN" =~ ^[A-Za-z0-9._-]+$ ]] || die "--left-hand-can contains unsupported characters"
[[ "$RIGHT_HAND_CAN" =~ ^[A-Za-z0-9._-]+$ ]] || die "--right-hand-can contains unsupported characters"
[[ "$ARMS" == "left,right" || "$ARMS" == "right" || "$ARMS" == "left" ]] || die "--arms must be left,right, left, or right"
LEFT_ENABLED=0; RIGHT_ENABLED=0
[[ "$ARMS" == *left* ]] && LEFT_ENABLED=1
[[ "$ARMS" == *right* ]] && RIGHT_ENABLED=1
(( LEFT_ENABLED || RIGHT_ENABLED )) || die "--arms must select at least one arm"
(( LEFT_ENABLED )) || [[ "$LEFT_TOUCH" == "false" ]] || die "--left-touch requires --arms to include left"
(( RIGHT_ENABLED )) || [[ "$RIGHT_TOUCH" == "false" ]] || die "--right-touch requires --arms to include right"
[[ -z "$EXPERIMENT_MANIFEST" || -f "$EXPERIMENT_MANIFEST" ]] || die "experiment manifest not found: $EXPERIMENT_MANIFEST"
if [[ -n "$EXPERIMENT_MANIFEST" ]]; then
  [[ "$CONDITION_ID" == "unassigned" ]] || die "--condition cannot override an immutable experiment manifest"
  "$SYSTEM_PYTHON" - "$EXPERIMENT_MANIFEST" <<'PY' || die "invalid experiment manifest"
import json
import sys
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
if manifest.get("schema") != "robot_teleop.experiment-manifest/v1":
    raise SystemExit("unsupported schema")
if manifest.get("domain") != "real":
    raise SystemExit("start_capture_session.sh requires a domain=real manifest")
for key in ("manifest_id", "condition_id", "task_id", "reference_revision", "policy_revision"):
    if not manifest.get(key):
        raise SystemExit(f"missing {key}")
PY
  read -r MANIFEST_EXPERIMENT_ID MANIFEST_CONDITION_ID MANIFEST_TASK_ID MANIFEST_OPERATOR_ID < <("$SYSTEM_PYTHON" - "$EXPERIMENT_MANIFEST" <<'PY'
import json
import sys
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
print(manifest["experiment_id"], manifest["condition_id"], manifest["task_id"], manifest["operator_id"])
PY
)
  EXPERIMENT_ID="$MANIFEST_EXPERIMENT_ID"
  CONDITION_ID="$MANIFEST_CONDITION_ID"
  TASK_ID="$MANIFEST_TASK_ID"
  OPERATOR_ID="$MANIFEST_OPERATOR_ID"
fi
if [[ -z "$EXPERIMENT_MANIFEST" ]]; then
  EXPERIMENT_ID="$(awk '/^experiment_id:/{print $2; exit}' "$EXPERIMENT_PROFILE")"
  [[ -n "$EXPERIMENT_ID" ]] || die "experiment_id missing from profile: $EXPERIMENT_PROFILE"
fi

if (( REAL )); then
  (( ESTOP_READY )) || die "real mode requires --physical-estop-ready"
  [[ "$CONFIRM" == "I_UNDERSTAND_REAL_ROBOT" ]] || die "real mode requires --confirm=I_UNDERSTAND_REAL_ROBOT"
  log "REAL MODE: teleop commands will be allowed after startup. Keep the physical E-stop reachable."

  # LinkerTA's vendor node attempts to run sudo when a SocketCAN interface is
  # down.  Fail before launching any ROS node so startup never hangs on a
  # hidden password prompt inside tmux.  Interface numbering is discovered at
  # runtime; LinkerTA itself probes all available CAN buses for master_arm.
  CAN_INTERFACES=()
  while IFS= read -r interface; do
    [[ -n "$interface" ]] && CAN_INTERFACES+=("$interface")
  done < <(compgen -G '/sys/class/net/can*' | xargs -r -n1 basename | sort -V)
  ((${#CAN_INTERFACES[@]})) || die "no SocketCAN canN interface detected; connect the PCAN adapter first"
  for interface in "${CAN_INTERFACES[@]}"; do
    operstate="$(cat "/sys/class/net/$interface/operstate" 2>/dev/null || true)"
    [[ "$operstate" == "up" ]] || die "$interface is $operstate; run: sudo bash scripts/enable_all_can.sh --confirm ENABLE_ALL_CAN_INTERFACES"
  done
else
  log "SAFE OBSERVATION MODE: teleop bridge will stay armed=false; no motion command reaches the robot."
fi

command -v tmux >/dev/null || die "tmux is not installed"
ROS_SETUP=""
for distro in "${ROS_DISTRO:-}" jazzy humble; do
  [[ -n "$distro" && -f "/opt/ros/$distro/setup.bash" ]] || continue
  ROS_SETUP="/opt/ros/$distro/setup.bash"
  break
done
[[ -n "$ROS_SETUP" ]] || die "no supported ROS2 setup found under /opt/ros"
set +u
source "$ROS_SETUP"
set -u
command -v ros2 >/dev/null || die "ros2 is unavailable after sourcing $ROS_SETUP"
[[ -f "$ROOT_DIR/ros2_ws/install/setup.bash" ]] || die "ROS2 workspace is not built"
[[ -f "$ROOT_DIR/scripts/record_episode.sh" ]] || die "recorder script is missing"

set +u
source "$ROOT_DIR/ros2_ws/install/setup.bash"
set -u

if tmux has-session -t "$SESSION" 2>/dev/null; then
  die "tmux session already exists: $SESSION (use tmux attach -t $SESSION or choose --session=...)"
fi

# Do not create a second driver, master, bridge, camera, preview, or recorder.
# Match executable path boundaries because Linux truncates comm names to 15
# characters and cannot represent realsense2_camera_node in pgrep -x output.
PROCESS_CHECKS=(
  "lbot_driver|(^|/)lbot_driver([[:space:]]|$)"
  "linkerta_node|(^|/)linkerta_node([[:space:]]|$)"
  "joint_mapping_bridge_node|(^|/)joint_mapping_bridge_node([[:space:]]|$)"
  "realsense2_camera_node|(^|/)realsense2_camera_node([[:space:]]|$)"
  "rqt_image_view|(^|/)rqt_image_view([[:space:]]|$)"
  "ros2 bag record|(^|/)ros2[[:space:]]+bag[[:space:]]+record([[:space:]]|$)"
  "RunEvidence capture|(^|/)runevidence[[:space:]]+run([[:space:]]|$)"
)
for check in "${PROCESS_CHECKS[@]}"; do
  label="${check%%|*}"
  pattern="${check#*|}"
  matches="$(pgrep -af "$pattern" || true)"
  if [[ -n "$matches" ]]; then
    echo "[CONFLICT] $label" >&2
    echo "$matches" >&2
    die "existing capture process detected; stop it explicitly before retrying"
  fi
done

# Process checks also catch nodes launched outside tmux. Query the ROS graph as
# a second guard for component containers and non-standard executable names.
EXISTING_NODES="$(timeout 5s ros2 node list 2>/dev/null | grep -E '^/(camera/camera|linkerta_node|joint_mapping_bridge_node|robot1/lbot_(main|left_arm|right_arm)_node)$' || true)"
if [[ -n "$EXISTING_NODES" ]]; then
  # The ROS graph daemon can retain stale names briefly after tmux is killed.
  # Process checks above are authoritative for this launcher; only reject the
  # graph listing when a corresponding live capture process still exists.
  LIVE_CAPTURE_PROCESSES="$(pgrep -af 'lbot_driver|linkerta_node|joint_mapping_bridge_node|realsense2_camera_node|teleop_control_bridge' || true)"
  if [[ -n "$LIVE_CAPTURE_PROCESSES" ]]; then
    echo "[CONFLICT] existing ROS2 nodes:" >&2
    echo "$EXISTING_NODES" >&2
    die "ROS2 capture graph is not clean; stop the listed nodes before retrying"
  fi
  log "WARN: ROS graph listed stale nodes, but no matching processes are running; continuing"
fi

"$SYSTEM_PYTHON" "$ROOT_DIR/scripts/preflight.py" --mode ros2

realsense_usb_count() {
  local device count=0 vendor product
  for device in /sys/bus/usb/devices/*; do
    [[ -r "$device/idVendor" && -r "$device/idProduct" ]] || continue
    vendor="$(<"$device/idVendor")"
    product="$(<"$device/idProduct")"
    [[ "$vendor" == "8086" && "$product" =~ ^0b(3a|5b|07)$ ]] && ((count += 1))
  done
  printf '%s\n' "$count"
}

if command -v rs-enumerate-devices >/dev/null 2>&1; then
  CAMERA_INFO="$(rs-enumerate-devices 2>&1)" || die "RealSense enumeration failed:\n$CAMERA_INFO"
  grep -Fq "$CAMERA_SERIAL" <<<"$CAMERA_INFO" || die "RealSense serial not detected: $CAMERA_SERIAL"
  [[ -z "$SECOND_CAMERA_SERIAL" ]] || grep -Fq "$SECOND_CAMERA_SERIAL" <<<"$CAMERA_INFO" || die "second RealSense serial not detected: $SECOND_CAMERA_SERIAL"
elif command -v lsusb >/dev/null 2>&1; then
  USB_INFO="$(lsusb 2>&1)" || die "lsusb failed:\n$USB_INFO"
  grep -Eqi 'Intel.*RealSense|8086:0b3a|8086:0b5b|8086:0b07' <<<"$USB_INFO" || die "RealSense USB device not detected"
  REALSENSE_COUNT="$(realsense_usb_count)"
  (( REALSENSE_COUNT >= 1 )) || die "RealSense USB device not detected in sysfs"
  if [[ -n "$SECOND_CAMERA_SERIAL" ]]; then
    (( REALSENSE_COUNT >= 2 )) || die "two RealSense USB devices are required for --second-camera-serial"
  fi
  log "rs-enumerate-devices is unavailable; verified $REALSENSE_COUNT RealSense USB device(s), but cannot validate librealsense serial arguments before launch"
else
  log "WARN: neither rs-enumerate-devices nor lsusb is available; camera detection skipped"
fi

ROBOT_IP="$(awk -F'"' '/slave_arm_ips:/{flag=1;next} flag && /- "/{print $2; exit}' "$ROOT_DIR/ros2_ws/src/teleop_control_bridge/config/hardware_teleop.yaml")"
[[ -n "$ROBOT_IP" ]] || die "cannot read robot IP from hardware_teleop.yaml"
if command -v ping >/dev/null 2>&1; then
  ping -c 1 -W 1 "$ROBOT_IP" >/dev/null || die "robot IP is unreachable: $ROBOT_IP"
fi

FREE_KB="$(df -Pk "$ROOT_DIR/evidence" | awk 'NR==2 {print $4}')"
(( FREE_KB > 8*1024*1024 )) || die "less than 8 GiB free under evidence filesystem"

CONFIG="$ROOT_DIR/ros2_ws/src/teleop_control_bridge/config/hardware_teleop.yaml"
grep -Eq 'enable_joint_limits:[[:space:]]*true' "$CONFIG" || die "joint limits are not enabled in hardware_teleop.yaml"
grep -Eq 'enable_one_euro_filter:[[:space:]]*true' "$CONFIG" || die "One-Euro filter is not enabled in hardware_teleop.yaml"

RUN_ROOT="${RUNEVIDENCE_ROOT:-$ROOT_DIR/evidence/teleop}"
[[ -n "$DATA_ROOT" ]] && RUN_ROOT="$DATA_ROOT"
RUNEVIDENCE_BIN="${RUNEVIDENCE_BIN:-$(command -v runevidence || true)}"
if [[ -z "$RUNEVIDENCE_BIN" && -x "$ROOT_DIR/.venv/runevidence/bin/runevidence" ]]; then
  RUNEVIDENCE_BIN="$ROOT_DIR/.venv/runevidence/bin/runevidence"
fi
[[ -n "$RUNEVIDENCE_BIN" && -x "$RUNEVIDENCE_BIN" ]] || die "RunEvidence not found; install it or set RUNEVIDENCE_BIN to its executable"
RUNEVIDENCE_PYTHON="$(dirname "$RUNEVIDENCE_BIN")/python3"
[[ -x "$RUNEVIDENCE_PYTHON" ]] || die "RunEvidence Python interpreter not found: $RUNEVIDENCE_PYTHON"
if (( PREVIEW )); then
  ros2 pkg prefix rqt_image_view >/dev/null 2>&1 || die "ROS package rqt_image_view is missing; install the matching ROS package or use --no-preview"
fi
mkdir -p "$RUN_ROOT"
[[ -w "$RUN_ROOT" ]] || die "data root is not writable: $RUN_ROOT"
export ROS_LOG_DIR="$RUN_ROOT/system/ros_logs"
mkdir -p "$ROS_LOG_DIR"
ARMED_ARG="false"
if (( REAL )); then ARMED_ARG="true"; fi

launch_cmd() {
  local title="$1"; shift
  tmux new-window -t "$SESSION" -n "$title" "bash -lc 'set +u; source \"$ROS_SETUP\"; source \"$ROOT_DIR/ros2_ws/install/setup.bash\"; set -u; export ROS_LOG_DIR=\"$ROS_LOG_DIR\"; $*; exec bash'"
}

wait_for_topic() {
  local topic="$1" timeout_s="$2" elapsed=0
  while (( elapsed < timeout_s )); do
    if ros2 topic list 2>/dev/null | grep -Fxq "$topic"; then
      log "topic ready: $topic"
      return 0
    fi
    sleep 1
    ((elapsed+=1))
  done
  die "topic did not appear within ${timeout_s}s: $topic (inspect tmux session: $SESSION)"
}

wait_for_tactile_modality() {
  local arm="$1" timeout_s="$2" elapsed=0
  local force="/cb_${arm}_hand_force"
  local matrix="/cb_${arm}_hand_matrix_touch"
  local mass="/cb_${arm}_hand_matrix_touch_mass"
  while (( elapsed < timeout_s )); do
    local listed
    listed="$(ros2 topic list 2>/dev/null || true)"
    if grep -Fxq "$force" <<<"$listed" || { grep -Fxq "$matrix" <<<"$listed" && grep -Fxq "$mass" <<<"$listed"; }; then
      log "tactile modality ready for $arm"
      return 0
    fi
    sleep 1
    ((elapsed+=1))
  done
  die "no supported tactile modality appeared for $arm within ${timeout_s}s"
}

tmux new-session -d -s "$SESSION" -n preflight "bash -lc 'echo robot teleoperation capture preflight passed; echo experiment=$EXPERIMENT_ID condition=$CONDITION_ID task=$TASK_ID operator=$OPERATOR_ID; echo mode=$([[ $REAL -eq 1 ]] && echo REAL_ARMED || echo SAFE_OBSERVATION); echo robot_ip=$ROBOT_IP; echo camera=$CAMERA_SERIAL ${WIDTH}x${HEIGHT}@${FPS}; exec bash'"
launch_cmd driver "ros2 launch lbot_driver lbot_start_driver.launch.py"
if (( LEFT_ENABLED )); then wait_for_topic /robot1/left_arm/joint_states 20; fi
if (( RIGHT_ENABLED )); then wait_for_topic /robot1/right_arm/joint_states 20; fi
launch_cmd camera "ros2 launch realsense2_camera rs_launch.py camera_namespace:=camera camera_name:=camera serial_no:=_$CAMERA_SERIAL enable_sync:=true align_depth.enable:=true rgb_camera.color_profile:=${WIDTH},${HEIGHT},${FPS} depth_module.depth_profile:=${WIDTH},${HEIGHT},${FPS}"
wait_for_topic /camera/camera/color/image_raw 30
wait_for_topic /camera/camera/aligned_depth_to_color/image_raw 30
CAMERA_NAMESPACES="$CAMERA_NAMESPACE"
if [[ -n "$SECOND_CAMERA_SERIAL" ]]; then
  SECOND_CAMERA_ROOT="${SECOND_CAMERA_NAMESPACE%/*}"
  SECOND_CAMERA_NAME="${SECOND_CAMERA_NAMESPACE##*/}"
  [[ -n "$SECOND_CAMERA_ROOT" && "$SECOND_CAMERA_ROOT" != "/" ]] || die "second camera namespace must include a namespace and camera name"
  launch_cmd camera2 "ros2 launch realsense2_camera rs_launch.py camera_namespace:=${SECOND_CAMERA_ROOT#/} camera_name:=$SECOND_CAMERA_NAME serial_no:=_$SECOND_CAMERA_SERIAL enable_sync:=true align_depth.enable:=true rgb_camera.color_profile:=${WIDTH},${HEIGHT},${FPS} depth_module.depth_profile:=${WIDTH},${HEIGHT},${FPS}"
  wait_for_topic "$SECOND_CAMERA_NAMESPACE/color/image_raw" 30
  wait_for_topic "$SECOND_CAMERA_NAMESPACE/aligned_depth_to_color/image_raw" 30
  CAMERA_NAMESPACES+=",$SECOND_CAMERA_NAMESPACE"
fi
export CAMERA_NAMESPACES
launch_cmd teleop "ros2 launch teleop_control_bridge hardware_teleop.launch.py launch_driver:=false armed:=$ARMED_ARG enable_left_arm:=$([[ $LEFT_ENABLED -eq 1 ]] && echo true || echo false) enable_right_arm:=$([[ $RIGHT_ENABLED -eq 1 ]] && echo true || echo false)"
if (( LEFT_ENABLED )); then
  wait_for_topic /left_arm_joint_control 20
  wait_for_topic /teleop/left/mapped_joint_command 20
fi
if (( RIGHT_ENABLED )); then
  wait_for_topic /right_arm_joint_control 20
  wait_for_topic /teleop/right/mapped_joint_command 20
fi
if (( HAND_SDK )); then
  # Explicit, disarmed SDK startup: tactile/state recording never enables hand motion.
  launch_cmd hands "ros2 launch hand_adapter hand_interface.launch.py armed:=false launch_left_sdk:=$([[ $LEFT_ENABLED -eq 1 ]] && echo true || echo false) launch_right_sdk:=$([[ $RIGHT_ENABLED -eq 1 ]] && echo true || echo false) left_can:=$LEFT_HAND_CAN right_can:=$RIGHT_HAND_CAN left_touch:=$LEFT_TOUCH right_touch:=$RIGHT_TOUCH initialize_pose:=false allow_sdk_commands:=false"
  if (( LEFT_ENABLED )); then wait_for_topic /cb_left_hand_state 20; fi
  if (( RIGHT_ENABLED )); then wait_for_topic /cb_right_hand_state 20; fi
  if [[ "$LEFT_TOUCH" == "true" ]]; then wait_for_tactile_modality left 20; fi
  if [[ "$RIGHT_TOUCH" == "true" ]]; then wait_for_tactile_modality right 20; fi
fi
if (( REAL )); then
  # Startup only verifies that LinkerTA/bridge topics are online.  Command
  # samples are checked by the recorder/quality gate after the operator starts
  # moving; requiring motion here creates a race at session startup.
  CAPTURE_PREFLIGHT=("$SYSTEM_PYTHON" "$ROOT_DIR/scripts/preflight.py" --mode capture --source real --arms "$ARMS" --sample-timeout-s 5)
  if [[ "$LEFT_TOUCH" == "true" || "$RIGHT_TOUCH" == "true" ]]; then
    CAPTURE_PREFLIGHT+=(--require-tactile)
  fi
  "${CAPTURE_PREFLIGHT[@]}"
else
  log "Capture-topic sample preflight is skipped in safe observation mode; run scripts/preflight.py --mode capture after teleop inputs are active."
fi
if (( PREVIEW )); then
  if [[ -n "${DISPLAY:-}" ]]; then
    # Keep one GUI process per RGB stream. They live in tmux windows and are
    # closed automatically with the capture session; the recorder TTY remains
    # independent of both viewers.
    launch_cmd preview_rgb1 "ros2 run rqt_image_view rqt_image_view /camera/camera/color/image_raw"
    if [[ -n "$SECOND_CAMERA_SERIAL" ]]; then
      launch_cmd preview_rgb2 "ros2 run rqt_image_view rqt_image_view ${SECOND_CAMERA_NAMESPACE%/}/color/image_raw"
    fi
  else
    log "WARN: DISPLAY is empty; camera preview window skipped"
  fi
fi
MONITOR_ARM="right"; (( LEFT_ENABLED && ! RIGHT_ENABLED )) && MONITOR_ARM="left"
launch_cmd monitor "while true; do date; ros2 topic hz /robot1/${MONITOR_ARM}_arm/joint_states --window 20 2>/dev/null | head -n 4; ros2 topic hz /camera/camera/color/image_raw --window 20 2>/dev/null | head -n 4; sleep 5; done"
launch_cmd sync "\"$SYSTEM_PYTHON\" \"$ROOT_DIR/tools/diagnose_time_sync.py\" --duration-s 10 --camera-namespace /camera/camera --output \"$RUN_ROOT/pre_capture_time_sync.json\""

# tmux windows inherit the server environment from session creation, not variables
# exported later in this launcher. Pass the resolved camera list explicitly so the
# recorder always captures every camera that passed preflight.
ANNOTATION_STATE="$RUN_ROOT/.annotation_state.json"
RECORDER_ENV="export CAMERA_NAMESPACES=\"$CAMERA_NAMESPACES\"; export TELEOP_CAPTURE_DURATION_S=$DURATION_S; export TELEOP_CAPTURE_MODE=$CAPTURE_MODE; export TELEOP_CAPTURE_EPISODES=$EPISODES; export TELEOP_CAPTURE_ARMS=$ARMS; export TELEOP_TACTILE_ENABLED=$([[ \"$LEFT_TOUCH\" == true || \"$RIGHT_TOUCH\" == true ]] && echo true || echo false); export TELEOP_HARDWARE_COMMANDS_ENABLED=$([[ $REAL -eq 1 ]] && echo true || echo false); export TELEOP_EXPERIMENT_ID=$EXPERIMENT_ID; export TELEOP_CONDITION_ID=$CONDITION_ID; export TELEOP_OPERATOR_ID=$OPERATOR_ID; export TELEOP_AUDITOR_ID=$AUDITOR_ID; export TELEOP_TASK_ID=$TASK_ID; export TELEOP_EXPERIMENT_PROFILE=$EXPERIMENT_PROFILE; export TELEOP_EXPERIMENT_MANIFEST=\"$EXPERIMENT_MANIFEST\"; export RUNEVIDENCE_BAG_COMPRESSION_MODE=file; export RUNEVIDENCE_BAG_COMPRESSION_FORMAT=zstd; export RUNEVIDENCE_ROOT=\"$RUN_ROOT\"; export RUNEVIDENCE_BIN=\"$RUNEVIDENCE_BIN\";"
RECORDER_ARGS="--runs-root \"$RUN_ROOT\" --episodes \"$EPISODES\" --arms \"$ARMS\" --cameras \"$CAMERA_NAMESPACES\" --experiment-id \"$EXPERIMENT_ID\" --condition-id \"$CONDITION_ID\" --operator-id \"$OPERATOR_ID\" --auditor-id \"$AUDITOR_ID\" --annotation-state \"$ANNOTATION_STATE\" --event-publisher-python \"$SYSTEM_PYTHON\" --task-id \"$TASK_ID\" --camera-profile \"${WIDTH}x${HEIGHT}x${FPS}\""
if [[ "$CAPTURE_MODE" == "timed" ]]; then
  RECORDER_ARGS+=" --auto-start --max-duration \"$DURATION_S\""
fi
launch_cmd recorder "$RECORDER_ENV \"$RUNEVIDENCE_PYTHON\" \"$ROOT_DIR/tools/capture_episode.py\" $RECORDER_ARGS; exec bash"

tmux select-window -t "$SESSION:preflight"
log "tmux session started: $SESSION"
log "attach: tmux attach -t $SESSION"
log "safe stop: tmux kill-session -t $SESSION (does not power off robot)"
log "Recorder waits for Enter before each episode; mode=$CAPTURE_MODE; output: $RUN_ROOT"
log "RGB previews: one window per configured camera; closed automatically with tmux session"
log "Same recorder window: Enter starts/stops; digit keys 1-9/0 annotate immediately"
log "To stop the whole session safely: bash $ROOT_DIR/scripts/stop_capture_session.sh"
