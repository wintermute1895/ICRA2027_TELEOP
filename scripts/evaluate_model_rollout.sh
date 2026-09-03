#!/usr/bin/env bash
# Stable read-only evaluator for a recorded model rollout.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROS_SETUP=""
for distro in "${ROS_DISTRO:-}" jazzy humble; do
  [[ -n "$distro" && -f "/opt/ros/$distro/setup.bash" ]] || continue
  ROS_SETUP="/opt/ros/$distro/setup.bash"
  break
done
[[ -n "$ROS_SETUP" ]] || { echo "[FATAL] ROS2 setup not found" >&2; exit 2; }
[[ -f "$ROOT_DIR/ros2_ws/install/setup.bash" ]] || { echo "[FATAL] ROS workspace is not built" >&2; exit 2; }
set +u
source "$ROS_SETUP"
source "$ROOT_DIR/ros2_ws/install/setup.bash"
set -u
exec /usr/bin/python3 "$ROOT_DIR/tools/evaluate_model_rollout.py" "$@"
