#!/usr/bin/env bash
# Launch the calibrated MuJoCo task scene without touching lbot_driver.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="$ROOT/assets/robots/linker_platform/sensorized/a7_l10_task_scene.mjcf.xml"
ROS_LOG_DIR="${ROS_LOG_DIR:-/tmp/ilex_ros_logs}"
MPC_PYTHON="${MPC_PYTHON:-/home/ilex/miniforge3/envs/mpc_env/bin/python}"

[[ -x "$MPC_PYTHON" ]] || { echo "[FATAL] MuJoCo Python missing: $MPC_PYTHON" >&2; exit 2; }
"$MPC_PYTHON" -B "$ROOT/tools/build_a7_task_scene.py"
[[ -f "$MODEL" ]] || { echo "[FATAL] task scene missing: $MODEL" >&2; exit 2; }
mkdir -p "$ROS_LOG_DIR"
source /opt/ros/humble/setup.bash
source "$ROOT/ros2_ws/install/setup.bash"

export ROS_LOG_DIR
exec ros2 launch sim_robot_driver sim_teleop.launch.py \
  "model_path:=$MODEL" \
  "render:=${RENDER:-true}" \
  "keyboard:=${KEYBOARD:-true}" \
  "input_mode:=${INPUT_MODE:-follow_joint}"
