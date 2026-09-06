#!/usr/bin/env bash
# Stable real/sim rollout entry. ROS2 uses system Python; ACT/filter workers
# are launched by their own environment-aware adapters.
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
[[ -f "$ROS_SETUP" ]] || { echo "[FATAL] ROS setup not found: $ROS_SETUP" >&2; exit 2; }
[[ -f "$ROOT_DIR/ros2_ws/install/setup.bash" ]] || { echo "[FATAL] ROS workspace is not built; run scripts/build_ros2_workspace.sh" >&2; exit 2; }
unset AMENT_PREFIX_PATH COLCON_PREFIX_PATH CMAKE_PREFIX_PATH PYTHONPATH
set +u
source "$ROS_SETUP"
source "$ROOT_DIR/ros2_ws/install/setup.bash"
set -u
exec /usr/bin/python3 "$ROOT_DIR/tools/run_model_rollout.py" "$@"
