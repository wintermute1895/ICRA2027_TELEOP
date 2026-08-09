#!/usr/bin/env bash
set -euo pipefail

# Record synchronized ROS2 topics into the RunEvidence run directory.
# This script never launches lbot_driver, linkerta, or any motion node.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${RUNEVIDENCE_RUN_DIR:-${ROOT_DIR}/evidence/teleop-standalone-$(date +%Y%m%d-%H%M%S)}"
DURATION="${TELEOP_CAPTURE_DURATION_S:-60}"
FINALIZE_TIMEOUT="${TELEOP_CAPTURE_FINALIZE_TIMEOUT_S:-300}"
COMPRESSION_MODE="${RUNEVIDENCE_BAG_COMPRESSION_MODE:-file}"
COMPRESSION_FORMAT="${RUNEVIDENCE_BAG_COMPRESSION_FORMAT:-zstd}"
# The stock realsense2_camera launch uses camera_namespace=camera and
# camera_name=camera, producing /camera/camera/<stream>. Keep it configurable
# for custom launch files.
CAMERA_NAMESPACE="${REALSENSE_NAMESPACE:-/camera/camera}"

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

ARTIFACT_DIR="${RUN_DIR}/artifacts"
BAG_DIR="${ARTIFACT_DIR}/rosbag2"
mkdir -p "$ARTIFACT_DIR"
if [[ -e "$BAG_DIR" ]]; then
  echo "Refusing to overwrite existing bag directory: $BAG_DIR" >&2
  exit 2
fi

TOPICS=(
  /left_arm_joint_control
  /right_arm_joint_control
  /teleop/left/master_joint_raw
  /teleop/left/master_joint_filtered
  /teleop/left/mapped_joint_command
  /teleop/right/master_joint_raw
  /teleop/right/master_joint_filtered
  /teleop/right/mapped_joint_command
  /robot1/left_arm/joint_states
  /robot1/right_arm/joint_states
  "${CAMERA_NAMESPACE}/color/image_raw"
  "${CAMERA_NAMESPACE}/color/camera_info"
  "${CAMERA_NAMESPACE}/aligned_depth_to_color/image_raw"
  "${CAMERA_NAMESPACE}/depth/camera_info"
  /tf
  /tf_static
)

python3 - "$ARTIFACT_DIR/teleop_capture_manifest.json" "$DURATION" "$CAMERA_NAMESPACE" "$COMPRESSION_MODE" "$COMPRESSION_FORMAT" "${TOPICS[@]}" <<'PY'
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
payload = {
    "schema": "robot_teleop.teleop-capture/v1",
    "episode_schema": "robot_teleop.episode/v1",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "experiment": {
        "experiment_id": os.environ.get("TELEOP_EXPERIMENT_ID", "unassigned"),
        "condition_id": os.environ.get("TELEOP_CONDITION_ID", "unassigned"),
        "operator_id": os.environ.get("TELEOP_OPERATOR_ID", "anonymous"),
        "task_id": os.environ.get("TELEOP_TASK_ID", "unspecified"),
        "profile": os.environ.get("TELEOP_EXPERIMENT_PROFILE"),
    },
    "duration_s": duration,
    "camera_namespace": camera_namespace,
    "camera_profile": "640x480x15",
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
    "canonical_fields": {
        "master_joint_source": "/left_arm_joint_control,/right_arm_joint_control",
        "master_joint_raw": "/teleop/left/master_joint_raw,/teleop/right/master_joint_raw",
        "master_joint_filtered": "/teleop/left/master_joint_filtered,/teleop/right/master_joint_filtered",
        "mapped_joint_command": "/teleop/left/mapped_joint_command,/teleop/right/mapped_joint_command",
        "robot_joint_state": "/robot1/left_arm/joint_states,/robot1/right_arm/joint_states",
        "camera_rgb": "<camera_namespace>/color/image_raw",
        "camera_depth": "<camera_namespace>/aligned_depth_to_color/image_raw",
        "camera_info": "<camera_namespace>/color/camera_info,<camera_namespace>/depth/camera_info",
        "tf": "/tf,/tf_static",
    },
}
output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

echo "Recording ${#TOPICS[@]} topics for ${DURATION}s into ${BAG_DIR}"
COMPRESSION_ARGS=()
if [[ "$COMPRESSION_MODE" != "none" ]]; then
  COMPRESSION_ARGS=(--compression-mode "$COMPRESSION_MODE" --compression-format "$COMPRESSION_FORMAT")
fi
set +e
timeout --signal=INT --kill-after="${FINALIZE_TIMEOUT}s" "${DURATION}s" \
  ros2 bag record \
    --storage sqlite3 \
    --output "$BAG_DIR" \
    "${COMPRESSION_ARGS[@]}" \
    "${TOPICS[@]}"
STATUS=$?
set -e
if [[ "$STATUS" != "0" && "$STATUS" != "124" ]]; then
  echo "ros2 bag record failed with status ${STATUS}" >&2
  exit "$STATUS"
fi

if [[ ! -s "${BAG_DIR}/metadata.yaml" ]] || \
   { ! compgen -G "${BAG_DIR}/*.db3" >/dev/null && ! compgen -G "${BAG_DIR}/*.db3.zstd" >/dev/null; }; then
  echo "ros2 bag did not produce metadata.yaml and a sqlite3 or zstd-compressed sqlite3 data file" >&2
  exit 3
fi

echo "Capture complete: ${RUN_DIR}"
