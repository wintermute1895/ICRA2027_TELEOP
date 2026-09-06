#!/usr/bin/env bash
set -euo pipefail

# Record synchronized ROS2 topics into the RunEvidence run directory.
# This script never launches lbot_driver, linkerta, or any motion node.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEM_PYTHON="${SYSTEM_PYTHON:-/usr/bin/python3}"
[[ -x "$SYSTEM_PYTHON" ]] || { echo "system Python not found: $SYSTEM_PYTHON" >&2; exit 2; }
RUN_DIR="${RUNEVIDENCE_RUN_DIR:-${ROOT_DIR}/evidence/teleop-standalone-$(date +%Y%m%d-%H%M%S)}"
DURATION="${TELEOP_CAPTURE_DURATION_S:-60}"
CAPTURE_MODE="${TELEOP_CAPTURE_MODE:-timed}"
FINALIZE_TIMEOUT="${TELEOP_CAPTURE_FINALIZE_TIMEOUT_S:-300}"
COMPRESSION_MODE="${RUNEVIDENCE_BAG_COMPRESSION_MODE:-file}"
COMPRESSION_FORMAT="${RUNEVIDENCE_BAG_COMPRESSION_FORMAT:-zstd}"
# The stock realsense2_camera launch uses camera_namespace=camera and
# camera_name=camera, producing /camera/camera/<stream>. Keep it configurable
# for custom launch files.
CAMERA_NAMESPACE="${REALSENSE_NAMESPACE:-/camera/camera}"
CAMERA_NAMESPACES="${CAMERA_NAMESPACES:-$CAMERA_NAMESPACE}"
ROBOT_STATE_NAMESPACE="${ROBOT_STATE_NAMESPACE:-/robot1}"
TELEOP_NAMESPACE="${TELEOP_NAMESPACE:-/teleop}"
SOURCE_DOMAIN="${SOURCE_DOMAIN:-real}"
CAPTURE_ARMS="${TELEOP_CAPTURE_ARMS:-left,right}"
SIM_CAMERA_NAMESPACES="${SIM_CAMERA_NAMESPACES:-}"
if [[ -n "$SIM_CAMERA_NAMESPACES" && "$CAMERA_NAMESPACES" != *"$SIM_CAMERA_NAMESPACES"* ]]; then
  CAMERA_NAMESPACES+=",$SIM_CAMERA_NAMESPACES"
fi

# ROS 2 may otherwise try to write under ~/.ros/log.  That is fragile on
# remote/managed machines and can make ros2 bag abort before recording starts.
# Keep recorder logs inside the evidence bundle by default.
export ROS_LOG_DIR="${ROS_LOG_DIR:-${RUN_DIR}/system/ros_logs}"
mkdir -p "$ROS_LOG_DIR"

if ! [[ "$DURATION" =~ ^[0-9]+([.][0-9]+)?$ ]] || [[ "$DURATION" == "0" ]]; then
  echo "TELEOP_CAPTURE_DURATION_S must be a positive number" >&2
  exit 2
fi
if ! [[ "$FINALIZE_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
  echo "TELEOP_CAPTURE_FINALIZE_TIMEOUT_S must be a positive integer" >&2
  exit 2
fi
[[ "$CAPTURE_MODE" == "timed" || "$CAPTURE_MODE" == "manual" ]] || {
  echo "TELEOP_CAPTURE_MODE must be timed or manual" >&2
  exit 2
}

ARTIFACT_DIR="${RUN_DIR}/artifacts"
BAG_DIR="${ARTIFACT_DIR}/rosbag2"
mkdir -p "$ARTIFACT_DIR"
if [[ -e "$BAG_DIR" ]]; then
  echo "Refusing to overwrite existing bag directory: $BAG_DIR" >&2
  exit 2
fi

# In manual sessions runevidence intentionally detaches stdin.  The tmux
# parent therefore controls stop through a small file instead of `read`.
CONTROL_FILE="${TELEOP_CAPTURE_CONTROL_FILE:-}"
RUN_MARKER="${TELEOP_CAPTURE_RUN_MARKER:-}"
BAG_PID_FILE="${TELEOP_CAPTURE_BAG_PID_FILE:-}"
if [[ -n "$RUN_MARKER" ]]; then
  printf '%s\n' "$RUN_DIR" > "$RUN_MARKER"
fi

IFS=',' read -r -a ARM_LIST <<< "$CAPTURE_ARMS"
(( ${#ARM_LIST[@]} )) || { echo "TELEOP_CAPTURE_ARMS must select an arm" >&2; exit 2; }
TOPICS=("${TELEOP_NAMESPACE}/events" "${TELEOP_NAMESPACE}/terminal_audit")
for arm in "${ARM_LIST[@]}"; do
  [[ "$arm" == "left" || "$arm" == "right" ]] || { echo "unsupported arm: $arm" >&2; exit 2; }
  TOPICS+=(
    "/${arm}_arm_joint_control"
    "${TELEOP_NAMESPACE}/${arm}/master_joint_raw"
    "${TELEOP_NAMESPACE}/${arm}/master_joint_filtered"
    "${TELEOP_NAMESPACE}/${arm}/mapped_joint_command"
    "/model_deployment/${arm}_arm_joint_control"
    "/model_deployment/diagnostics"
    "/teleop_filter/${arm}/master_joint_raw_rad"
    "/teleop_filter/${arm}/master_joint_filtered_rad"
    "/teleop_filter/${arm}/diagnostics"
    "${ROBOT_STATE_NAMESPACE}/${arm}_arm/joint_states"
    "${ROBOT_STATE_NAMESPACE}/${arm}_arm/vendor_command"
    "${ROBOT_STATE_NAMESPACE}/${arm}_arm/pose_states"
    "${ROBOT_STATE_NAMESPACE}/${arm}_hand/control_cmd"
    "${ROBOT_STATE_NAMESPACE}/${arm}_hand/joint_states"
    "${TELEOP_NAMESPACE}/${arm}/gripper_state"
    "${TELEOP_NAMESPACE}/${arm}/task_context"
  )
done

if [[ -n "$CAMERA_NAMESPACES" ]]; then
  IFS=',' read -r -a CAPTURE_CAMERAS <<< "$CAMERA_NAMESPACES"
  for camera in "${CAPTURE_CAMERAS[@]}"; do
    camera="${camera%/}"
    [[ -n "$camera" ]] || continue
    TOPICS+=(
      "${camera}/color/image_raw"
      "${camera}/aligned_depth_to_color/image_raw"
      "${camera}/color/camera_info"
      "${camera}/depth/camera_info"
    )
  done
fi

if [[ "$SOURCE_DOMAIN" == "sim" ]]; then
  TOPICS+=(
    "${ROBOT_STATE_NAMESPACE}/left_arm/filter_context"
    "${ROBOT_STATE_NAMESPACE}/right_arm/filter_context"
  )
fi

if [[ "$SOURCE_DOMAIN" == "real" ]]; then
  for arm in "${ARM_LIST[@]}"; do
    TOPICS+=("/cb_${arm}_hand_state" "/cb_${arm}_hand_info" "/cb_${arm}_hand_force" "/cb_${arm}_hand_matrix_touch" "/cb_${arm}_hand_matrix_touch_mass")
  done
fi

TOPICS+=(
  /tf
  /tf_static
)
# Keep the topic list deterministic and avoid duplicate subscriptions when
# multiple arms share a diagnostics topic.
mapfile -t TOPICS < <(printf '%s\n' "${TOPICS[@]}" | awk '!seen[$0]++')

"$SYSTEM_PYTHON" - "$ARTIFACT_DIR/teleop_capture_manifest.json" "$DURATION" "$CAMERA_NAMESPACE" "$COMPRESSION_MODE" "$COMPRESSION_FORMAT" "${TOPICS[@]}" <<'PY'
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

output = pathlib.Path(sys.argv[1])
duration = float(sys.argv[2])
camera_namespace = sys.argv[3]
compression_mode = sys.argv[4]
compression_format = sys.argv[5]
topics = sys.argv[6:]
hardware_commands_enabled = os.environ.get("TELEOP_HARDWARE_COMMANDS_ENABLED", "false").lower() == "true"
tactile_enabled = os.environ.get("TELEOP_TACTILE_ENABLED", "false").lower() == "true"
robot_state_namespace = os.environ.get("ROBOT_STATE_NAMESPACE", "/robot1").rstrip("/")
teleop_namespace = os.environ.get("TELEOP_NAMESPACE", "/teleop").rstrip("/")
source_domain = os.environ.get("SOURCE_DOMAIN", "real")
experiment_manifest_path = os.environ.get("TELEOP_EXPERIMENT_MANIFEST", "")
experiment_manifest = None
experiment_manifest_sha256 = None
if experiment_manifest_path:
    manifest_file = pathlib.Path(experiment_manifest_path)
    if not manifest_file.is_file():
        raise SystemExit(f"experiment manifest not found: {manifest_file}")
    experiment_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if experiment_manifest.get("schema") != "robot_teleop.experiment-manifest/v1":
        raise SystemExit("experiment manifest has an unsupported schema")
    if experiment_manifest.get("domain") != source_domain:
        raise SystemExit(f"manifest domain {experiment_manifest.get('domain')} does not match SOURCE_DOMAIN={source_domain}")
    experiment_manifest_sha256 = __import__("hashlib").sha256(manifest_file.read_bytes()).hexdigest()

def experiment_value(name, fallback, default):
    if experiment_manifest is None:
        return fallback
    manifest_value = experiment_manifest.get(name)
    if manifest_value is None:
        return fallback
    if fallback != default and fallback != manifest_value:
        raise SystemExit(f"{name} conflicts with immutable experiment manifest")
    return manifest_value

camera_namespaces = [item.rstrip("/") for item in os.environ.get("CAMERA_NAMESPACES", camera_namespace).split(",") if item]
payload = {
    "schema": "robot_teleop.teleop-capture/v1",
    "episode_schema": "robot_teleop.episode/v1",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "experiment": {
        "experiment_id": experiment_value("experiment_id", os.environ.get("TELEOP_EXPERIMENT_ID", "unassigned"), "unassigned"),
        "condition_id": experiment_value("condition_id", os.environ.get("TELEOP_CONDITION_ID", "unassigned"), "unassigned"),
        "operator_id": experiment_value("operator_id", os.environ.get("TELEOP_OPERATOR_ID", "anonymous"), "anonymous"),
        "task_id": experiment_value("task_id", os.environ.get("TELEOP_TASK_ID", "unspecified"), "unspecified"),
        "profile": os.environ.get("TELEOP_EXPERIMENT_PROFILE"),
        "manifest_id": None if experiment_manifest is None else experiment_manifest["manifest_id"],
        "manifest_sha256": experiment_manifest_sha256,
        "manifest": experiment_manifest,
    },
    "duration_s": duration,
    "capture_mode": os.environ.get("TELEOP_CAPTURE_MODE", "timed"),
    "source_domain": source_domain,
    "capture_arms": [item for item in os.environ.get("TELEOP_CAPTURE_ARMS", "left,right").split(",") if item],
    "camera_namespace": camera_namespace,
    "camera_namespaces": camera_namespaces,
    "camera_profile": os.environ.get("CAMERA_PROFILE", "640x480x15"),
    "bag_compression": {
        "mode": compression_mode,
        "format": compression_format
    },
    "timestamp_policy": {
        "primary": "ROS2 message header.stamp",
        "robot_state_preferred_source": "controller sec/nanosec mapped into ROS epoch using a per-arm receipt-time offset; driver receipt time is fallback",
        "camera_source": "RealSense ROS2 driver ROS timestamp; device hardware timestamp must be diagnosed separately",
        "bag_storage": "rosbag2 storage time is receipt time; message header.stamp is retained in serialized messages",
        "cross_sensor_requirement": "camera and robot topics must use the same ROS clock",
    },
    "topics": topics,
    "units": {
        "robot_joint_state_position": "rad (ROS2 lbot_driver state topic)",
        "robot_joint_state_velocity": "rad/s",
        "master_control_position": "source-defined; verify LinkerTA publisher",
    },
    "hardware_commands_enabled": hardware_commands_enabled,
    "motion_commands_published": hardware_commands_enabled,
    "tactile": {
        "availability": "available" if source_domain == "real" and tactile_enabled else "unavailable",
        "unavailable_reason": None if source_domain == "real" and tactile_enabled else ("not_enabled_for_capture" if source_domain == "real" else "not_integrated_in_simulation"),
        "topics_recorded": [topic for topic in topics if topic.startswith("/cb_")],
    },
    "recorded_fields": {
        "master_joint_source": "/left_arm_joint_control,/right_arm_joint_control",
        "master_joint_raw": f"{teleop_namespace}/left/master_joint_raw,{teleop_namespace}/right/master_joint_raw",
        "master_joint_filtered": f"{teleop_namespace}/left/master_joint_filtered,{teleop_namespace}/right/master_joint_filtered",
        "mapped_joint_command": f"{teleop_namespace}/left/mapped_joint_command,{teleop_namespace}/right/mapped_joint_command",
        "model_deployment_output": "/model_deployment/left_arm_joint_control,/model_deployment/right_arm_joint_control",
        "model_deployment_diagnostics": "/model_deployment/diagnostics",
        "learned_filter_raw": "/teleop_filter/left/master_joint_raw_rad,/teleop_filter/right/master_joint_raw_rad",
        "learned_filter_output": "/teleop_filter/left/master_joint_filtered_rad,/teleop_filter/right/master_joint_filtered_rad",
        "robot_joint_state": f"{robot_state_namespace}/left_arm/joint_states,{robot_state_namespace}/right_arm/joint_states",
        "controller_command": f"{robot_state_namespace}/left_arm/vendor_command,{robot_state_namespace}/right_arm/vendor_command",
        "tcp_pose": f"{robot_state_namespace}/left_arm/pose_states,{robot_state_namespace}/right_arm/pose_states",
        "task_context": f"{teleop_namespace}/left/task_context,{teleop_namespace}/right/task_context",
        "events": f"{teleop_namespace}/events,{teleop_namespace}/terminal_audit",
        "hand_command": f"{robot_state_namespace}/left_hand/control_cmd,{robot_state_namespace}/right_hand/control_cmd",
        "hand_state": f"{robot_state_namespace}/left_hand/joint_states,{robot_state_namespace}/right_hand/joint_states",
        "gripper_state": {
            "left": f"{teleop_namespace}/left/gripper_state",
            "right": f"{teleop_namespace}/right/gripper_state",
            "encoding": "std_msgs/msg/UInt8",
            "semantics": {"0": "open", "1": "closed"},
            "timestamp_source": "rosbag_receipt_time_for_headerless_message",
            "model_input": "binary_gripper_state",
        },
        "hand_state_raw": "/cb_left_hand_state,/cb_right_hand_state",
        "hand_info_raw": "/cb_left_hand_info,/cb_right_hand_info",
        "tactile_force": "/cb_left_hand_force,/cb_right_hand_force",
        "tactile_matrix": "/cb_left_hand_matrix_touch,/cb_right_hand_matrix_touch",
        "tactile_mass": "/cb_left_hand_matrix_touch_mass,/cb_right_hand_matrix_touch_mass",
        "camera_rgb": ",".join(f"{namespace}/color/image_raw" for namespace in camera_namespaces),
        "camera_depth": ",".join(f"{namespace}/aligned_depth_to_color/image_raw" for namespace in camera_namespaces),
        "camera_info": ",".join(f"{namespace}/color/camera_info,{namespace}/depth/camera_info" for namespace in camera_namespaces),
        "tf": "/tf,/tf_static",
    },
}
output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

echo "Recording ${#TOPICS[@]} topics into ${BAG_DIR} (mode=${CAPTURE_MODE})"
COMPRESSION_ARGS=()
if [[ "$COMPRESSION_MODE" != "none" ]]; then
  COMPRESSION_ARGS=(--compression-mode "$COMPRESSION_MODE" --compression-format "$COMPRESSION_FORMAT")
fi
set +e
if [[ "$CAPTURE_MODE" == "manual" ]]; then
  # Run rosbag in its own process group.  Signalling only the ros2 CLI wrapper
  # can leave the recorder child running or skip its metadata finalization.
  setsid ros2 bag record \
    --disable-keyboard-controls \
    --storage sqlite3 \
    --output "$BAG_DIR" \
    "${COMPRESSION_ARGS[@]}" \
    "${TOPICS[@]}" < /dev/null &
  BAG_PID=$!
  [[ -n "$BAG_PID_FILE" ]] && printf '%s\n' "$BAG_PID" > "$BAG_PID_FILE"
  echo "RECORDING_STARTED pid=${BAG_PID}"
  if [[ -n "$CONTROL_FILE" ]]; then
    while [[ ! -s "$CONTROL_FILE" ]]; do sleep 0.2; done
  else
    read -r -p "正在录制。回车结束并保存本条数据（遥操保持运行）: "
  fi
  kill -INT -- "-$BAG_PID" 2>/dev/null || kill -INT "$BAG_PID" 2>/dev/null || true
  # Wait for a clean shutdown, but never block forever on a recorder that did
  # not handle SIGINT.  The database is checked independently of exit status.
  finalize_deadline=$((SECONDS + 60))
  while kill -0 "$BAG_PID" 2>/dev/null && (( SECONDS < finalize_deadline )); do
    sleep 1
  done
  if kill -0 "$BAG_PID" 2>/dev/null; then
    echo "rosbag did not exit after 60s; sending TERM" >&2
    kill -TERM -- "-$BAG_PID" 2>/dev/null || kill -TERM "$BAG_PID" 2>/dev/null || true
    sleep 2
  fi
  if kill -0 "$BAG_PID" 2>/dev/null; then
    echo "rosbag still alive; sending KILL" >&2
    kill -KILL -- "-$BAG_PID" 2>/dev/null || kill -KILL "$BAG_PID" 2>/dev/null || true
  fi
  wait "$BAG_PID" 2>/dev/null || true
  STATUS=0
else
  timeout --signal=INT --kill-after="${FINALIZE_TIMEOUT}s" "${DURATION}s" \
    ros2 bag record \
      --disable-keyboard-controls \
      --storage sqlite3 \
      --output "$BAG_DIR" \
      "${COMPRESSION_ARGS[@]}" \
      "${TOPICS[@]}" < /dev/null
  STATUS=$?
fi
set -e
if [[ "$STATUS" != "0" && "$STATUS" != "124" && "$STATUS" != "130" ]]; then
  echo "ros2 bag record failed with status ${STATUS}" >&2
  exit "$STATUS"
fi

if [[ ! -s "${BAG_DIR}/metadata.yaml" ]]; then
  # A forced stop can leave a valid SQLite bag without metadata.  rosbag2's
  # reindex reconstructs metadata from the database without changing samples.
  if compgen -G "${BAG_DIR}/*.db3" >/dev/null || compgen -G "${BAG_DIR}/*.db3.zstd" >/dev/null; then
    echo "metadata.yaml missing; attempting ros2 bag reindex" >&2
    ros2 bag reindex "$BAG_DIR" >/dev/null 2>&1 || true
  fi
fi
if [[ ! -s "${BAG_DIR}/metadata.yaml" ]] || \
   { ! compgen -G "${BAG_DIR}/*.db3" >/dev/null && ! compgen -G "${BAG_DIR}/*.db3.zstd" >/dev/null; }; then
  echo "ros2 bag did not produce a complete metadata.yaml + sqlite3 artifact" >&2
  exit 3
fi

# Terminal outcome is deliberately collected after rosbag shutdown.  Ctrl-C
# stops recording, then this prompt is the only path that can create a terminal
# audit for the episode.  No geometric success is inferred here.
AUDIT_PATH="${ARTIFACT_DIR}/terminal_audit.json"
EPISODE_ID="${TELEOP_EPISODE_ID:-$(basename "$RUN_DIR")}"
AUDIT_TOOL="${ROOT_DIR}/tools/finalize_episode_audit.py"
if [[ "${TELEOP_INTERACTIVE_AUDIT:-true}" == "true" ]]; then
    while true; do
      read -r -p "本次任务是否成功？[y/N]: " OUTCOME
      case "${OUTCOME,,}" in
        y|yes) SUCCESS_ARGS=(--success); break ;;
        n|no|"") SUCCESS_ARGS=(--failure); break ;;
        *) echo "请输入 y 或 n" >&2 ;;
      esac
    done
    read -r -p "终止原因（必填）: " TERMINATION_REASON
    [[ -n "$TERMINATION_REASON" ]] || TERMINATION_REASON="operator_unspecified"
    read -r -p "是否发生安全事件？[y/N]: " SAFETY
    read -r -p "是否有未记录的外部接管？[y/N]: " OVERRIDE
    SAFETY_ARGS=(); OVERRIDE_ARGS=()
    [[ "${SAFETY,,}" == "y" || "${SAFETY,,}" == "yes" ]] && SAFETY_ARGS=(--safety-violation)
    [[ "${OVERRIDE,,}" == "y" || "${OVERRIDE,,}" == "yes" ]] && OVERRIDE_ARGS=(--unlogged-external-override)
    /usr/bin/python3 "$AUDIT_TOOL" --output "$AUDIT_PATH" --episode-id "$EPISODE_ID" \
      "${SUCCESS_ARGS[@]}" --termination-reason "$TERMINATION_REASON" \
      --operator-id "${TELEOP_OPERATOR_ID:-anonymous}" "${SAFETY_ARGS[@]}" "${OVERRIDE_ARGS[@]}" \
      --evidence-ref "$BAG_DIR"
else
  echo "TELEOP_INTERACTIVE_AUDIT=false: parent will write terminal audit" >&2
fi

echo "Capture complete: ${RUN_DIR}"
