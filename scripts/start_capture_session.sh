#!/usr/bin/env bash
# One-command, tmux-based robot teleoperation capture launcher.
# Safe by default: the teleop bridge is started with armed=false.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="teleop_capture"
DURATION_S="30"
EPISODES="2"
REAL=0
ESTOP_READY=0
CONFIRM=""
CAMERA_SERIAL="261722075670"
CAMERA_NAMESPACE="/camera/camera"
WIDTH=640
HEIGHT=480
FPS=15
PREVIEW=1
EXPERIMENT_PROFILE="$ROOT_DIR/config/experiments/precision_assembly_ab.yaml"
CONDITION_ID="unassigned"
OPERATOR_ID="anonymous"
TASK_ID="unspecified"
EXPERIMENT_MANIFEST=""

usage() {
  cat >&2 <<'EOF'
Usage:
  start_capture_session.sh [options]

Safe default starts the real-robot driver and recorder but keeps teleop armed=false.
Options:
  --real                         allow armed=true (still requires both confirmations)
  --physical-estop-ready        confirm physical E-stop is reachable
  --confirm=I_UNDERSTAND_REAL_ROBOT
  --duration-s SEC               episode duration (default: 30)
  --episodes N                   number of episodes (default: 2)
  --session NAME                 tmux session name (default: teleop_capture)
  --no-preview                   do not open rqt_image_view
  --camera-serial SERIAL         RealSense serial (default: 261722075670)
  --experiment-profile PATH      experiment profile YAML
  --condition=ID                 legacy condition metadata; formal runs use --experiment-manifest
  --operator-id=ID               de-identified operator ID
  --task-id=ID                   task/fixture identifier
  --experiment-manifest PATH     immutable manifest from tools/resolve_experiment_manifest.py
EOF
}

die() { echo "[FATAL] $*" >&2; exit 2; }
log() { echo "[teleop-capture] $*"; }

for arg in "$@"; do
  case "$arg" in
    --real) REAL=1 ;;
    --physical-estop-ready) ESTOP_READY=1 ;;
    --confirm=*) CONFIRM="${arg#*=}" ;;
    --duration-s=*) DURATION_S="${arg#*=}" ;;
    --episodes=*) EPISODES="${arg#*=}" ;;
    --session=*) SESSION="${arg#*=}" ;;
    --no-preview) PREVIEW=0 ;;
    --camera-serial=*) CAMERA_SERIAL="${arg#*=}" ;;
    --experiment-profile=*) EXPERIMENT_PROFILE="${arg#*=}" ;;
    --condition=*) CONDITION_ID="${arg#*=}" ;;
    --operator-id=*) OPERATOR_ID="${arg#*=}" ;;
    --task-id=*) TASK_ID="${arg#*=}" ;;
    --experiment-manifest=*) EXPERIMENT_MANIFEST="${arg#*=}" ;;
    -h|--help) usage; exit 0 ;;
    *) usage; die "unknown option: $arg" ;;
  esac
done

[[ "$DURATION_S" =~ ^[1-9][0-9]*$ ]] || die "--duration-s must be a positive integer"
[[ "$EPISODES" =~ ^[1-9][0-9]*$ ]] || die "--episodes must be a positive integer"
(( ${#SESSION} <= 40 )) || die "tmux session name is too long"
[[ -f "$EXPERIMENT_PROFILE" ]] || die "experiment profile not found: $EXPERIMENT_PROFILE"
[[ "$CONDITION_ID" =~ ^[A-Za-z0-9._-]+$ ]] || die "--condition contains unsupported characters"
[[ "$OPERATOR_ID" =~ ^[A-Za-z0-9._-]+$ ]] || die "--operator-id contains unsupported characters"
[[ "$TASK_ID" =~ ^[A-Za-z0-9._-]+$ ]] || die "--task-id contains unsupported characters"
[[ -z "$EXPERIMENT_MANIFEST" || -f "$EXPERIMENT_MANIFEST" ]] || die "experiment manifest not found: $EXPERIMENT_MANIFEST"
if [[ -n "$EXPERIMENT_MANIFEST" ]]; then
  [[ "$CONDITION_ID" == "unassigned" ]] || die "--condition cannot override an immutable experiment manifest"
  python3 - "$EXPERIMENT_MANIFEST" <<'PY' || die "invalid experiment manifest"
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
  read -r MANIFEST_EXPERIMENT_ID MANIFEST_CONDITION_ID MANIFEST_TASK_ID MANIFEST_OPERATOR_ID < <(python3 - "$EXPERIMENT_MANIFEST" <<'PY'
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
EXPERIMENT_ID="$(awk '/^experiment_id:/{print $2; exit}' "$EXPERIMENT_PROFILE")"
[[ -n "$EXPERIMENT_ID" ]] || die "experiment_id missing from profile: $EXPERIMENT_PROFILE"

if (( REAL )); then
  (( ESTOP_READY )) || die "real mode requires --physical-estop-ready"
  [[ "$CONFIRM" == "I_UNDERSTAND_REAL_ROBOT" ]] || die "real mode requires --confirm=I_UNDERSTAND_REAL_ROBOT"
  log "REAL MODE: teleop commands will be allowed after startup. Keep the physical E-stop reachable."
else
  log "SAFE OBSERVATION MODE: teleop bridge will stay armed=false; no motion command reaches the robot."
fi

command -v tmux >/dev/null || die "tmux is not installed"
command -v ros2 >/dev/null || die "ros2 is not on PATH; source /opt/ros/humble/setup.bash first"
[[ -f /opt/ros/humble/setup.bash ]] || die "ROS2 Humble setup not found"
[[ -f "$ROOT_DIR/ros2_ws/install/setup.bash" ]] || die "ROS2 workspace is not built"
[[ -f "$ROOT_DIR/scripts/record_episode.sh" ]] || die "recorder script is missing"

set +u
source /opt/ros/humble/setup.bash
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
  echo "[CONFLICT] existing ROS2 nodes:" >&2
  echo "$EXISTING_NODES" >&2
  die "ROS2 capture graph is not clean; stop the listed nodes before retrying"
fi

python3 "$ROOT_DIR/scripts/preflight.py" --mode ros2

if command -v rs-enumerate-devices >/dev/null 2>&1; then
  CAMERA_INFO="$(rs-enumerate-devices 2>&1)" || die "RealSense enumeration failed:\n$CAMERA_INFO"
  grep -Fq "$CAMERA_SERIAL" <<<"$CAMERA_INFO" || die "RealSense serial not detected: $CAMERA_SERIAL"
elif command -v lsusb >/dev/null 2>&1; then
  USB_INFO="$(lsusb 2>&1)" || die "lsusb failed:\n$USB_INFO"
  grep -Eqi 'Intel.*RealSense|8086:0b3a|8086:0b07' <<<"$USB_INFO" || die "RealSense USB device not detected"
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
RUNEVIDENCE_BIN="${RUNEVIDENCE_BIN:-/home/ilex/miniforge3/envs/mpc_env/bin/runevidence}"
[[ -x "$RUNEVIDENCE_BIN" ]] || die "RunEvidence not found: $RUNEVIDENCE_BIN"
if (( PREVIEW )); then
  ros2 pkg prefix rqt_image_view >/dev/null 2>&1 || die "ROS package rqt_image_view is missing; install ros-humble-rqt-image-view or use --no-preview"
fi
mkdir -p "$RUN_ROOT"
export ROS_LOG_DIR="$RUN_ROOT/system/ros_logs"
mkdir -p "$ROS_LOG_DIR"
ARMED_ARG="false"
if (( REAL )); then ARMED_ARG="true"; fi

launch_cmd() {
  local title="$1"; shift
  tmux new-window -t "$SESSION" -n "$title" "bash -lc 'set +u; source /opt/ros/humble/setup.bash; source \"$ROOT_DIR/ros2_ws/install/setup.bash\"; set -u; export ROS_LOG_DIR=\"$ROS_LOG_DIR\"; $*; exec bash'"
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

tmux new-session -d -s "$SESSION" -n preflight "bash -lc 'echo robot teleoperation capture preflight passed; echo experiment=$EXPERIMENT_ID condition=$CONDITION_ID task=$TASK_ID operator=$OPERATOR_ID; echo mode=$([[ $REAL -eq 1 ]] && echo REAL_ARMED || echo SAFE_OBSERVATION); echo robot_ip=$ROBOT_IP; echo camera=$CAMERA_SERIAL ${WIDTH}x${HEIGHT}@${FPS}; exec bash'"
launch_cmd driver "ros2 launch lbot_driver lbot_start_driver.launch.py"
wait_for_topic /robot1/left_arm/joint_states 20
wait_for_topic /robot1/right_arm/joint_states 20
launch_cmd camera "ros2 launch realsense2_camera rs_launch.py camera_namespace:=camera camera_name:=camera serial_no:=_$CAMERA_SERIAL enable_sync:=true align_depth.enable:=true rgb_camera.color_profile:=${WIDTH},${HEIGHT},${FPS} depth_module.depth_profile:=${WIDTH},${HEIGHT},${FPS}"
wait_for_topic /camera/camera/color/image_raw 30
wait_for_topic /camera/camera/aligned_depth_to_color/image_raw 30
launch_cmd teleop "ros2 launch teleop_control_bridge hardware_teleop.launch.py launch_driver:=false armed:=$ARMED_ARG"
wait_for_topic /left_arm_joint_control 20
wait_for_topic /right_arm_joint_control 20
wait_for_topic /teleop/left/mapped_joint_command 20
wait_for_topic /teleop/right/mapped_joint_command 20
if (( PREVIEW )); then
  if [[ -n "${DISPLAY:-}" ]]; then
    launch_cmd preview "ros2 run rqt_image_view rqt_image_view /camera/camera/color/image_raw"
  else
    log "WARN: DISPLAY is empty; camera preview window skipped"
  fi
fi
launch_cmd monitor "while true; do date; ros2 topic hz /robot1/left_arm/joint_states --window 20 2>/dev/null | head -n 4; ros2 topic hz /camera/camera/color/image_raw --window 20 2>/dev/null | head -n 4; sleep 5; done"
launch_cmd sync "python3 \"$ROOT_DIR/tools/diagnose_time_sync.py\" --duration-s 10 --camera-namespace /camera/camera --output \"$RUN_ROOT/pre_capture_time_sync.json\""

RECORDER="$ROOT_DIR/scripts/record_episode.sh"
launch_cmd recorder "for i in \$(seq 1 $EPISODES); do export TELEOP_CAPTURE_DURATION_S=$DURATION_S; export TELEOP_HARDWARE_COMMANDS_ENABLED=$([[ $REAL -eq 1 ]] && echo true || echo false); export TELEOP_EXPERIMENT_ID=$EXPERIMENT_ID; export TELEOP_CONDITION_ID=$CONDITION_ID; export TELEOP_OPERATOR_ID=$OPERATOR_ID; export TELEOP_TASK_ID=$TASK_ID; export TELEOP_EXPERIMENT_PROFILE=$EXPERIMENT_PROFILE; export TELEOP_EXPERIMENT_MANIFEST=\"$EXPERIMENT_MANIFEST\"; export RUNEVIDENCE_BAG_COMPRESSION_MODE=file; export RUNEVIDENCE_BAG_COMPRESSION_FORMAT=zstd; echo READY_EPISODE_\$i; read -r -p \"按回车开始 episode \$i（Ctrl-C 可中止）: \"; \"$RUNEVIDENCE_BIN\" run --domain robotics --runs-root \"$RUN_ROOT\" --label \"$EXPERIMENT_ID-$CONDITION_ID-episode-\$i\" --input experiment_id=\"$EXPERIMENT_ID\" --input condition_id=\"$CONDITION_ID\" --input operator_id=\"$OPERATOR_ID\" --input task_id=\"$TASK_ID\" --input experiment_profile=\"$EXPERIMENT_PROFILE\" --input camera_serial=\"$CAMERA_SERIAL\" --input camera_profile=\"${WIDTH}x${HEIGHT}x${FPS}\" --input teleop_armed=\"$ARMED_ARG\" --input teleop_config=\"$CONFIG\" -- bash \"$RECORDER\"; done; echo ALL_EPISODES_COMPLETE; exec bash"

tmux select-window -t "$SESSION:preflight"
log "tmux session started: $SESSION"
log "attach: tmux attach -t $SESSION"
log "safe stop: tmux kill-session -t $SESSION (does not power off robot)"
log "Recorder waits for Enter before each episode; output: $RUN_ROOT"
