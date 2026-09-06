#!/usr/bin/env bash
# Build and launch the simulation-only USB-C insertion teleoperation scene.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MPC_PYTHON="${MPC_PYTHON:-/home/ilex/miniforge3/envs/mpc_env/bin/python}"
MODEL="$ROOT/assets/robots/linker_platform/sensorized/a7_l10_usb_c_insertion.mjcf.xml"

[[ -x "$MPC_PYTHON" ]] || { echo "[FATAL] MuJoCo Python missing: $MPC_PYTHON" >&2; exit 2; }
"$MPC_PYTHON" -B "$ROOT/tools/build_a7_usb_c_insertion_scene.py"
# ROS Humble's generated setup scripts read optional variables before they are
# initialized, so source them with nounset temporarily disabled.
set +u
source /opt/ros/humble/setup.bash
source "$ROOT/ros2_ws/install/setup.bash"
set -u

exec ros2 launch sim_robot_driver sim_teleop.launch.py \
  "model_path:=$MODEL" \
  "render:=${RENDER:-true}" \
  "keyboard:=${KEYBOARD:-true}" \
  "input_mode:=${INPUT_MODE:-follow_joint}" \
  left_hand_model:=L10 right_hand_model:=L10
