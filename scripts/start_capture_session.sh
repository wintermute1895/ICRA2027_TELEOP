#!/usr/bin/env bash
# One-command robot teleoperation capture launcher. Supports tmux windows or
# direct background processes; the recorder remains a normal Python TTY app.
# Safe by default: the teleop bridge is started with armed=false.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# ROS 2 Jazzy and its Python extensions are installed against the system
# interpreter.  Keep capture tooling independent of an activated Conda shell.
SYSTEM_PYTHON="${SYSTEM_PYTHON:-/usr/bin/python3}"
[[ -x "$SYSTEM_PYTHON" ]] || { echo "[FATAL] system Python not found: $SYSTEM_PYTHON" >&2; exit 2; }
CONFIG_FILE="${CAPTURE_CONFIG:-$ROOT_DIR/config/capture_session.env}"
DATA_ROOT="${CAPTURE_DATA_ROOT:-}"
# Resolve the requested configuration before applying defaults. Supporting
# both --config=PATH and --config PATH avoids option-order-dependent behavior.
ARGS=("$@")
for ((index = 0; index < ${#ARGS[@]}; index++)); do
  case "${ARGS[index]}" in
    --config=*) CONFIG_FILE="${ARGS[index]#*=}" ;;
    --config)
      ((index += 1))
      CONFIG_FILE="${ARGS[index]:-}"
      ;;
  esac
done
if [[ "$CONFIG_FILE" != /* ]]; then CONFIG_FILE="$ROOT_DIR/$CONFIG_FILE"; fi
[[ -f "$CONFIG_FILE" ]] || { echo "[FATAL] config file not found: $CONFIG_FILE" >&2; exit 2; }
# shellcheck disable=SC1090
source "$CONFIG_FILE"
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
TASK_PROFILE=""
TASK_BUNDLE_ID=""
TASK_BUNDLE_REVISION=""
TASK_BUNDLE_SHA256=""
EXPERIMENT_MANIFEST=""
HAND_SDK=0
LEFT_HAND_CAN="can0"
RIGHT_HAND_CAN="can1"
LEFT_TOUCH="false"
RIGHT_TOUCH="false"
ARMS="left,right"
LEARNED_FILTER_CONFIG=""
MODEL_DEPLOYMENT_CONFIG="$ROOT_DIR/config/runtime/model_deployment.yaml"
LAUNCH_MODE="${CAPTURE_LAUNCH_MODE:-tmux}"

usage() {
  cat >&2 <<'EOF'
Usage:
  start_capture_session.sh [options]

Safe default starts the real-robot driver and recorder but keeps teleop armed=false.
Options:
  --config=PATH                  load session defaults (default: config/capture_session.env)
  --data-root PATH               store RunEvidence directly on an external disk
  --real                         allow armed=true (still requires both confirmations)
  --physical-estop-ready        confirm physical E-stop is reachable
  --confirm=I_UNDERSTAND_REAL_ROBOT
  --duration-s SEC               timed episode duration / metadata field (default: 30)
  --episodes N                   number of episodes; 0 keeps the recorder ready until q (default: 2)
  --manual-segments              recorder window: Enter=start, Enter=stop/save, q=end session
  --session NAME                 tmux session name (default: teleop_capture)
  --launch-mode MODE             tmux (default) or direct
  --no-preview                   do not open rqt_image_view
  --camera-serial SERIAL         RealSense serial (default: 261722075670)
  --second-camera-serial SERIAL  optional second RealSense serial
  --second-camera-namespace NS   second RGB-D namespace (default: /camera2/camera)
  --experiment-profile PATH      experiment profile YAML
  --condition=ID                 legacy condition metadata; formal runs use --experiment-manifest
  --operator-id=ID               de-identified operator ID
  --auditor-id=ID                second-person keyboard auditor ID
  --task-id=ID                   task/fixture identifier
  --task-profile PATH            versioned task bundle (preferred task selector)
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
validate_config_bool() {
  local name="$1" value="${!1:-false}"
  [[ "$value" == true || "$value" == false ]] || die "$name must be true or false in $CONFIG_FILE"
}

# Apply config-file defaults first; explicit CLI options below override them.
for name in CAPTURE_REAL CAPTURE_MANUAL_SEGMENTS CAPTURE_NO_PREVIEW CAPTURE_HAND_SDK CAPTURE_LEFT_TOUCH CAPTURE_RIGHT_TOUCH; do
  validate_config_bool "$name"
done
[[ "${CAPTURE_REAL:-false}" == true ]] && die "CAPTURE_REAL=true is not allowed in config; pass --real explicitly"
[[ -n "${CAPTURE_ARMS:-}" ]] && ARMS="$CAPTURE_ARMS"
[[ -n "${CAPTURE_SESSION:-}" ]] && SESSION="$CAPTURE_SESSION"
[[ -n "${CAPTURE_DURATION_S:-}" ]] && DURATION_S="$CAPTURE_DURATION_S"
[[ -n "${CAPTURE_EPISODES:-}" ]] && EPISODES="$CAPTURE_EPISODES"
[[ -n "${CAPTURE_CAMERA_SERIAL:-}" ]] && CAMERA_SERIAL="$CAPTURE_CAMERA_SERIAL"
[[ -n "${CAPTURE_CAMERA_NAMESPACE:-}" ]] && CAMERA_NAMESPACE="$CAPTURE_CAMERA_NAMESPACE"
[[ -n "${CAPTURE_SECOND_CAMERA_SERIAL:-}" ]] && SECOND_CAMERA_SERIAL="$CAPTURE_SECOND_CAMERA_SERIAL"
[[ -n "${CAPTURE_SECOND_CAMERA_NAMESPACE:-}" ]] && SECOND_CAMERA_NAMESPACE="$CAPTURE_SECOND_CAMERA_NAMESPACE"
[[ -n "${CAPTURE_WIDTH:-}" ]] && WIDTH="$CAPTURE_WIDTH"
[[ -n "${CAPTURE_HEIGHT:-}" ]] && HEIGHT="$CAPTURE_HEIGHT"
[[ -n "${CAPTURE_FPS:-}" ]] && FPS="$CAPTURE_FPS"
[[ -n "${CAPTURE_TASK_PROFILE:-}" ]] && TASK_PROFILE="$CAPTURE_TASK_PROFILE"
[[ -n "${CAPTURE_EXPERIMENT_PROFILE:-}" ]] && EXPERIMENT_PROFILE="$CAPTURE_EXPERIMENT_PROFILE"
[[ -n "${CAPTURE_CONDITION_ID:-}" ]] && CONDITION_ID="$CAPTURE_CONDITION_ID"
[[ -n "${CAPTURE_TASK_ID:-}" ]] && TASK_ID="$CAPTURE_TASK_ID"
[[ -n "${CAPTURE_OPERATOR_ID:-}" ]] && OPERATOR_ID="$CAPTURE_OPERATOR_ID"
[[ -n "${CAPTURE_AUDITOR_ID:-}" ]] && AUDITOR_ID="$CAPTURE_AUDITOR_ID"
[[ -n "${CAPTURE_EXPERIMENT_MANIFEST:-}" ]] && EXPERIMENT_MANIFEST="$CAPTURE_EXPERIMENT_MANIFEST"
[[ "${CAPTURE_MANUAL_SEGMENTS:-false}" == true ]] && CAPTURE_MODE="manual"
[[ "${CAPTURE_NO_PREVIEW:-false}" == true ]] && PREVIEW=0
[[ "${CAPTURE_HAND_SDK:-false}" == true ]] && HAND_SDK=1
[[ -n "${CAPTURE_LEFT_HAND_CAN:-}" ]] && LEFT_HAND_CAN="$CAPTURE_LEFT_HAND_CAN"
[[ -n "${CAPTURE_RIGHT_HAND_CAN:-}" ]] && RIGHT_HAND_CAN="$CAPTURE_RIGHT_HAND_CAN"
[[ "${CAPTURE_LEFT_TOUCH:-false}" == true ]] && LEFT_TOUCH="true"
[[ "${CAPTURE_RIGHT_TOUCH:-false}" == true ]] && RIGHT_TOUCH="true"
[[ -n "${CAPTURE_DATA_ROOT:-}" ]] && DATA_ROOT="$CAPTURE_DATA_ROOT"
[[ -n "${CAPTURE_LEARNED_FILTER_CONFIG:-}" ]] && LEARNED_FILTER_CONFIG="$CAPTURE_LEARNED_FILTER_CONFIG"
[[ -n "${CAPTURE_MODEL_DEPLOYMENT_CONFIG:-}" ]] && MODEL_DEPLOYMENT_CONFIG="$CAPTURE_MODEL_DEPLOYMENT_CONFIG"
[[ "$EXPERIMENT_PROFILE" == /* ]] || EXPERIMENT_PROFILE="$ROOT_DIR/$EXPERIMENT_PROFILE"
if [[ -n "$EXPERIMENT_MANIFEST" && "$EXPERIMENT_MANIFEST" != /* ]]; then
  EXPERIMENT_MANIFEST="$ROOT_DIR/$EXPERIMENT_MANIFEST"
fi
if [[ -n "$TASK_PROFILE" && "$TASK_PROFILE" != /* ]]; then
  TASK_PROFILE="$ROOT_DIR/$TASK_PROFILE"
fi
if [[ -n "$LEARNED_FILTER_CONFIG" && "$LEARNED_FILTER_CONFIG" != /* ]]; then
  LEARNED_FILTER_CONFIG="$ROOT_DIR/$LEARNED_FILTER_CONFIG"
fi
if [[ "$MODEL_DEPLOYMENT_CONFIG" != /* ]]; then MODEL_DEPLOYMENT_CONFIG="$ROOT_DIR/$MODEL_DEPLOYMENT_CONFIG"; fi

for ((arg_index = 0; arg_index < ${#ARGS[@]}; arg_index++)); do
  arg="${ARGS[arg_index]}"
  case "$arg" in
    --config=*) ;;
    --config) ((arg_index += 1)) ;;
    --data-root=*) DATA_ROOT="${arg#*=}" ;;
    --real) REAL=1 ;;
    --physical-estop-ready) ESTOP_READY=1 ;;
    --confirm=*) CONFIRM="${arg#*=}" ;;
    --duration-s=*) DURATION_S="${arg#*=}" ;;
    --episodes=*) EPISODES="${arg#*=}" ;;
    --manual-segments) CAPTURE_MODE="manual" ;;
    --session=*) SESSION="${arg#*=}" ;;
    --launch-mode=*) LAUNCH_MODE="${arg#*=}" ;;
    --no-preview) PREVIEW=0 ;;
    --camera-serial=*) CAMERA_SERIAL="${arg#*=}" ;;
    --second-camera-serial=*) SECOND_CAMERA_SERIAL="${arg#*=}" ;;
    --second-camera-namespace=*) SECOND_CAMERA_NAMESPACE="${arg#*=}" ;;
    --experiment-profile=*) EXPERIMENT_PROFILE="${arg#*=}" ;;
    --condition=*) CONDITION_ID="${arg#*=}" ;;
    --operator-id=*) OPERATOR_ID="${arg#*=}" ;;
    --auditor-id=*) AUDITOR_ID="${arg#*=}" ;;
    --task-id=*) TASK_ID="${arg#*=}" ;;
    --task-profile=*) TASK_PROFILE="${arg#*=}" ;;
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

if [[ -n "$TASK_PROFILE" && "$TASK_PROFILE" != /* ]]; then
  TASK_PROFILE="$ROOT_DIR/$TASK_PROFILE"
fi

[[ "$DURATION_S" =~ ^[1-9][0-9]*$ ]] || die "--duration-s must be a positive integer"
[[ "$EPISODES" =~ ^[0-9]+$ ]] || die "--episodes must be a non-negative integer"
[[ "$WIDTH" =~ ^[1-9][0-9]*$ && "$HEIGHT" =~ ^[1-9][0-9]*$ && "$FPS" =~ ^[1-9][0-9]*$ ]] || die "camera width, height and fps must be positive integers"
(( ${#SESSION} <= 40 )) || die "tmux session name is too long"
[[ "$LAUNCH_MODE" == "tmux" || "$LAUNCH_MODE" == "direct" ]] || die "--launch-mode must be tmux or direct"
[[ -f "$EXPERIMENT_PROFILE" ]] || die "experiment profile not found: $EXPERIMENT_PROFILE"
if [[ -n "$TASK_PROFILE" ]]; then
  [[ -f "$TASK_PROFILE" || -d "$TASK_PROFILE" ]] || die "task profile not found: $TASK_PROFILE"
  TASK_BUNDLE_JSON="$($SYSTEM_PYTHON "$ROOT_DIR/tools/resolve_task_bundle.py" --task "$TASK_PROFILE")" || die "invalid task bundle: $TASK_PROFILE"
  read -r TASK_BUNDLE_ID TASK_BUNDLE_REVISION < <(printf '%s\n' "$TASK_BUNDLE_JSON" | "$SYSTEM_PYTHON" -c 'import json,sys; value=json.load(sys.stdin); print(value["task_id"], value["task_revision"])')
  if [[ "$TASK_ID" != "unspecified" && "$TASK_ID" != "$TASK_BUNDLE_ID" ]]; then
    die "CAPTURE_TASK_ID ($TASK_ID) disagrees with task bundle ($TASK_BUNDLE_ID)"
  fi
  TASK_ID="$TASK_BUNDLE_ID"
fi
TASK_REVISION=""
if [[ -n "$TASK_PROFILE" ]]; then
  TASK_REVISION="$TASK_BUNDLE_REVISION"
  TASK_BUNDLE_SHA256="$(printf '%s\n' "$TASK_BUNDLE_JSON" | "$SYSTEM_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["task_bundle_sha256"])')"
fi
[[ "$CONDITION_ID" =~ ^[A-Za-z0-9._-]+$ ]] || die "--condition contains unsupported characters"
[[ "$OPERATOR_ID" =~ ^[A-Za-z0-9._-]+$ ]] || die "--operator-id contains unsupported characters"
[[ "$AUDITOR_ID" =~ ^[A-Za-z0-9._-]+$ ]] || die "--auditor-id contains unsupported characters"
[[ "$TASK_ID" =~ ^[A-Za-z0-9._-]+$ ]] || die "--task-id contains unsupported characters"
[[ "$CAMERA_NAMESPACE" =~ ^/[A-Za-z0-9_/-]+$ ]] || die "--camera-namespace contains unsupported characters"
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
  if [[ -n "$TASK_PROFILE" && "$MANIFEST_TASK_ID" != "$TASK_BUNDLE_ID" ]]; then
    die "experiment manifest task_id ($MANIFEST_TASK_ID) disagrees with task bundle ($TASK_BUNDLE_ID)"
  fi
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

if [[ "$LAUNCH_MODE" == "tmux" ]]; then
  command -v tmux >/dev/null || die "tmux is not installed"
fi
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
[[ -f "$ROOT_DIR/tools/capture_episode.py" ]] || die "Python recorder is missing"

set +u
source "$ROOT_DIR/ros2_ws/install/setup.bash"
set -u

if [[ "$LAUNCH_MODE" == "tmux" ]] && tmux has-session -t "$SESSION" 2>/dev/null; then
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
  "model deployment supervisor|model_deployment_supervisor.py"
  "learned filter worker|learned_filter_worker.py"
  "ACT adapter|act_ros_adapter.py"
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

CONFIG="$ROOT_DIR/ros2_ws/src/teleop_control_bridge/config/hardware_teleop.yaml"
grep -Eq 'enable_joint_limits:[[:space:]]*true' "$CONFIG" || die "joint limits are not enabled in hardware_teleop.yaml"
grep -Eq 'enable_one_euro_filter:[[:space:]]*true' "$CONFIG" || die "One-Euro filter is not enabled in hardware_teleop.yaml"

RUN_ROOT="${RUNEVIDENCE_ROOT:-$ROOT_DIR/evidence/teleop}"
[[ -n "$DATA_ROOT" ]] && RUN_ROOT="$DATA_ROOT"
if [[ ! -d "$RUN_ROOT" ]]; then
  mkdir -p "$RUN_ROOT" 2>/dev/null || die "capture data root is not writable: $RUN_ROOT (check external disk mount; use CAPTURE_DATA_ROOT to override)"
fi
[[ -w "$RUN_ROOT" ]] || die "capture data root is not writable: $RUN_ROOT (disk may be mounted read-only)"
FREE_KB="$(df -Pk "$RUN_ROOT" | awk 'NR==2 {print $4}')"
(( FREE_KB > 8*1024*1024 )) || die "less than 8 GiB free under capture data filesystem"
RUNEVIDENCE_BIN="${RUNEVIDENCE_BIN:-$(command -v runevidence || true)}"
if [[ -z "$RUNEVIDENCE_BIN" && -x "$ROOT_DIR/.venv/runevidence/bin/runevidence" ]]; then
  RUNEVIDENCE_BIN="$ROOT_DIR/.venv/runevidence/bin/runevidence"
fi
[[ -n "$RUNEVIDENCE_BIN" && -x "$RUNEVIDENCE_BIN" ]] || die "RunEvidence not found; install it or set RUNEVIDENCE_BIN to its executable"
RUNEVIDENCE_PYTHON="$(dirname "$RUNEVIDENCE_BIN")/python3"
[[ -x "$RUNEVIDENCE_PYTHON" ]] || die "RunEvidence Python interpreter not found: $RUNEVIDENCE_PYTHON"
if (( PREVIEW )); then
  ros2 pkg prefix rqt_image_view >/dev/null 2>&1 || die "ROS package rqt_image_view is missing; install the matching ROS package or use --no-preview"
  RQT_IMAGE_VIEW_EXEC="$(ros2 pkg prefix rqt_image_view)/lib/rqt_image_view/rqt_image_view"
  [[ -x "$RQT_IMAGE_VIEW_EXEC" ]] || die "rqt_image_view executable not found: $RQT_IMAGE_VIEW_EXEC"
  "$SYSTEM_PYTHON" -c 'import rqt_gui, rclpy' >/dev/null 2>&1 || die "ROS GUI modules are unavailable in SYSTEM_PYTHON=$SYSTEM_PYTHON; source the ROS environment or set SYSTEM_PYTHON=/usr/bin/python3"
fi
mkdir -p "$RUN_ROOT"
[[ -w "$RUN_ROOT" ]] || die "data root is not writable: $RUN_ROOT"
export ROS_LOG_DIR="$RUN_ROOT/system/ros_logs"
mkdir -p "$ROS_LOG_DIR"
ARMED_ARG="false"
if (( REAL )); then ARMED_ARG="true"; fi

LAUNCHED_PIDS=()
launch_cmd() {
  local title="$1"; shift
  if [[ "$LAUNCH_MODE" == "tmux" ]]; then
    tmux new-window -t "$SESSION" -n "$title" "bash -lc 'set +u; source \"$ROS_SETUP\"; source \"$ROOT_DIR/ros2_ws/install/setup.bash\"; set -u; export ROS_LOG_DIR=\"$ROS_LOG_DIR\"; $*; exec bash'"
  else
    bash -lc "set +u; source '$ROS_SETUP'; source '$ROOT_DIR/ros2_ws/install/setup.bash'; set -u; export ROS_LOG_DIR='$ROS_LOG_DIR'; $*" &
    LAUNCHED_PIDS+=("$!")
  fi
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

if [[ "$LAUNCH_MODE" == "tmux" ]]; then
  tmux new-session -d -s "$SESSION" -n preflight "bash -lc 'echo robot teleoperation capture preflight passed; echo experiment=$EXPERIMENT_ID condition=$CONDITION_ID task=$TASK_ID operator=$OPERATOR_ID; echo mode=$([[ $REAL -eq 1 ]] && echo REAL_ARMED || echo SAFE_OBSERVATION); echo robot_ip=$ROBOT_IP; echo camera=$CAMERA_SERIAL ${WIDTH}x${HEIGHT}@${FPS}; exec bash'"
fi
# A tmux server can outlive a previous desktop session.  Explicitly refresh
# GUI variables so viewers use the current display/authentication context.
if [[ "$LAUNCH_MODE" == "tmux" ]]; then
  for gui_var in DISPLAY XAUTHORITY XDG_RUNTIME_DIR WAYLAND_DISPLAY; do
    if [[ -n "${!gui_var:-}" ]]; then
      tmux set-environment -t "$SESSION" "$gui_var" "${!gui_var}"
    else
      tmux set-environment -t "$SESSION" -r "$gui_var" 2>/dev/null || true
    fi
  done
fi
launch_cmd driver "ros2 launch lbot_driver lbot_start_driver.launch.py"
if (( LEFT_ENABLED )); then wait_for_topic /robot1/left_arm/joint_states 20; fi
if (( RIGHT_ENABLED )); then wait_for_topic /robot1/right_arm/joint_states 20; fi
CAMERA_ROOT="${CAMERA_NAMESPACE%/*}"
CAMERA_NAME="${CAMERA_NAMESPACE##*/}"
[[ -n "$CAMERA_ROOT" && "$CAMERA_ROOT" != "/" && -n "$CAMERA_NAME" ]] || die "camera namespace must include a namespace and camera name"
launch_cmd camera "ros2 launch realsense2_camera rs_launch.py camera_namespace:=${CAMERA_ROOT#/} camera_name:=$CAMERA_NAME serial_no:=_$CAMERA_SERIAL enable_sync:=true align_depth.enable:=true rgb_camera.color_profile:=${WIDTH},${HEIGHT},${FPS} depth_module.depth_profile:=${WIDTH},${HEIGHT},${FPS}"
wait_for_topic "$CAMERA_NAMESPACE/color/image_raw" 30
wait_for_topic "$CAMERA_NAMESPACE/aligned_depth_to_color/image_raw" 30
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
MASTER_LEFT_TOPIC=/left_arm_joint_control
MASTER_RIGHT_TOPIC=/right_arm_joint_control
MODEL_SOURCE=teleop
MODEL_CANDIDATE_ARGS=""
if [[ -n "$LEARNED_FILTER_CONFIG" ]]; then
  [[ -f "$LEARNED_FILTER_CONFIG" ]] || die "learned-filter config not found: $LEARNED_FILTER_CONFIG"
  read -r FILTER_ARM FILTER_OUTPUT_TOPIC < <("$SYSTEM_PYTHON" - "$LEARNED_FILTER_CONFIG" <<'PY'
import sys, yaml
config = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
if config.get("enabled") is not True:
    raise SystemExit("learned filter config is not enabled")
print(config["arm"], config["master_output_topic"])
PY
  )
  case "$FILTER_ARM" in
    left) : ;;
    right) : ;;
    *) die "learned-filter arm must be left or right: $FILTER_ARM" ;;
  esac
  MODEL_SOURCE=filter
  MODEL_CANDIDATE_ARGS="--filter-config=\"$LEARNED_FILTER_CONFIG\""
fi
if [[ "$MODEL_SOURCE" != teleop ]]; then
  [[ -f "$MODEL_DEPLOYMENT_CONFIG" ]] || die "model deployment config not found: $MODEL_DEPLOYMENT_CONFIG"
  "$SYSTEM_PYTHON" - "$MODEL_DEPLOYMENT_CONFIG" <<'PY' || die "model deployment config must have enabled: true"
import sys, yaml
config = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
if config.get("enabled") is not True:
    raise SystemExit(1)
PY
  launch_cmd deployment "bash \"$ROOT_DIR/scripts/start_model_deployment.sh\" \"$MODEL_DEPLOYMENT_CONFIG\" --shadow --source=$MODEL_SOURCE $MODEL_CANDIDATE_ARGS"
fi
MASTER_LEFT_TOPIC=/left_arm_joint_control
if (( RIGHT_ENABLED )) && [[ "$MODEL_SOURCE" != teleop ]]; then MASTER_RIGHT_TOPIC=/model_deployment/right_arm_joint_control; fi
launch_cmd teleop "ros2 launch teleop_control_bridge hardware_teleop.launch.py launch_driver:=false armed:=$ARMED_ARG enable_left_arm:=$([[ $LEFT_ENABLED -eq 1 ]] && echo true || echo false) enable_right_arm:=$([[ $RIGHT_ENABLED -eq 1 ]] && echo true || echo false) master_left_topic:=$MASTER_LEFT_TOPIC master_right_topic:=$MASTER_RIGHT_TOPIC"
if (( LEFT_ENABLED )); then
  wait_for_topic /left_arm_joint_control 20
  wait_for_topic /teleop/left/mapped_joint_command 20
fi
if (( RIGHT_ENABLED )); then
  wait_for_topic /right_arm_joint_control 20
  if [[ "$MODEL_SOURCE" != teleop ]]; then
    wait_for_topic /model_deployment/right_arm_joint_control 20
  fi
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
  if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    # Keep one GUI process per RGB stream. They live in tmux windows and are
    # closed automatically with the capture session; the recorder TTY remains
    # independent of both viewers.
    launch_cmd preview_rgb1 "exec \"$SYSTEM_PYTHON\" \"$RQT_IMAGE_VIEW_EXEC\" \"${CAMERA_NAMESPACE%/}/color/image_raw\""
    if [[ -n "$SECOND_CAMERA_SERIAL" ]]; then
      launch_cmd preview_rgb2 "exec \"$SYSTEM_PYTHON\" \"$RQT_IMAGE_VIEW_EXEC\" \"${SECOND_CAMERA_NAMESPACE%/}/color/image_raw\""
    fi
  else
    log "WARN: DISPLAY is empty; camera preview window skipped"
  fi
fi
MONITOR_ARM="right"; (( LEFT_ENABLED && ! RIGHT_ENABLED )) && MONITOR_ARM="left"
launch_cmd monitor "while true; do date; ros2 topic hz /robot1/${MONITOR_ARM}_arm/joint_states --window 20 2>/dev/null | head -n 4; ros2 topic hz ${CAMERA_NAMESPACE%/}/color/image_raw --window 20 2>/dev/null | head -n 4; sleep 5; done"
launch_cmd sync "\"$SYSTEM_PYTHON\" \"$ROOT_DIR/tools/diagnose_time_sync.py\" --duration-s 10 --camera-namespace \"$CAMERA_NAMESPACE\" --output \"$RUN_ROOT/pre_capture_time_sync.json\""

# tmux windows inherit the server environment from session creation, not variables
# exported later in this launcher. Pass the resolved camera list explicitly so the
# recorder always captures every camera that passed preflight.
ANNOTATION_STATE="$RUN_ROOT/.annotation_state.json"
RECORDER_ENV="export CAMERA_NAMESPACES=\"$CAMERA_NAMESPACES\"; export TELEOP_CAPTURE_DURATION_S=$DURATION_S; export TELEOP_CAPTURE_MODE=$CAPTURE_MODE; export TELEOP_CAPTURE_EPISODES=$EPISODES; export TELEOP_CAPTURE_ARMS=$ARMS; export TELEOP_TACTILE_ENABLED=$([[ \"$LEFT_TOUCH\" == true || \"$RIGHT_TOUCH\" == true ]] && echo true || echo false); export TELEOP_HARDWARE_COMMANDS_ENABLED=$([[ $REAL -eq 1 ]] && echo true || echo false); export TELEOP_EXPERIMENT_ID=$EXPERIMENT_ID; export TELEOP_CONDITION_ID=$CONDITION_ID; export TELEOP_OPERATOR_ID=$OPERATOR_ID; export TELEOP_AUDITOR_ID=$AUDITOR_ID; export TELEOP_TASK_ID=$TASK_ID; export TELEOP_TASK_REVISION=$TASK_REVISION; export TELEOP_TASK_BUNDLE=$TASK_PROFILE; export TELEOP_TASK_BUNDLE_SHA256=$TASK_BUNDLE_SHA256; export TELEOP_EXPERIMENT_PROFILE=$EXPERIMENT_PROFILE; export TELEOP_EXPERIMENT_MANIFEST=\"$EXPERIMENT_MANIFEST\"; export RUNEVIDENCE_BAG_COMPRESSION_MODE=file; export RUNEVIDENCE_BAG_COMPRESSION_FORMAT=zstd; export RUNEVIDENCE_ROOT=\"$RUN_ROOT\"; export RUNEVIDENCE_BIN=\"$RUNEVIDENCE_BIN\";"
RECORDER_ARGS="--runs-root \"$RUN_ROOT\" --episodes \"$EPISODES\" --arms \"$ARMS\" --cameras \"$CAMERA_NAMESPACES\" --experiment-id \"$EXPERIMENT_ID\" --condition-id \"$CONDITION_ID\" --operator-id \"$OPERATOR_ID\" --auditor-id \"$AUDITOR_ID\" --annotation-state \"$ANNOTATION_STATE\" --event-publisher-python \"$SYSTEM_PYTHON\" --task-id \"$TASK_ID\" --task-revision \"$TASK_REVISION\" --task-bundle \"$TASK_PROFILE\" --task-bundle-sha256 \"$TASK_BUNDLE_SHA256\" --camera-profile \"${WIDTH}x${HEIGHT}x${FPS}\""
if [[ "$CAPTURE_MODE" == "timed" ]]; then
  RECORDER_ARGS+=" --auto-start --max-duration \"$DURATION_S\""
fi
if [[ "$LAUNCH_MODE" == "tmux" ]]; then
  launch_cmd recorder "$RECORDER_ENV \"$RUNEVIDENCE_PYTHON\" \"$ROOT_DIR/tools/capture_episode.py\" $RECORDER_ARGS; exec bash"
else
  # Keep the recorder in the caller's terminal so manual Enter/digit input is
  # unambiguous. Other ROS processes remain in the background and are cleaned
  # up by stop_capture_session.sh.
  eval "$RECORDER_ENV \"$RUNEVIDENCE_PYTHON\" \"$ROOT_DIR/tools/capture_episode.py\" $RECORDER_ARGS"
fi

if [[ "$LAUNCH_MODE" == "tmux" ]]; then
  tmux select-window -t "$SESSION:preflight"
  log "tmux session started: $SESSION"
  log "attach: tmux attach -t $SESSION"
  log "safe stop: tmux kill-session -t $SESSION (does not power off robot)"
else
  log "direct processes started: ${LAUNCHED_PIDS[*]}"
  log "safe stop: bash $ROOT_DIR/scripts/stop_capture_session.sh"
fi
log "Recorder waits for Enter before each episode; mode=$CAPTURE_MODE; output: $RUN_ROOT"
log "RGB previews: one window per configured camera; closed automatically with tmux session"
log "Same recorder window: Enter starts/stops; digit keys 1-9/0 annotate immediately"
log "To stop the whole session safely: bash $ROOT_DIR/scripts/stop_capture_session.sh"
