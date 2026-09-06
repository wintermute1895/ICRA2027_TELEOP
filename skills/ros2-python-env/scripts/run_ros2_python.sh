#!/usr/bin/env bash
set -Eeuo pipefail

ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
[[ -f "$ROS_SETUP" ]] || { echo "[FATAL] ROS setup not found: $ROS_SETUP" >&2; exit 2; }
(( $# > 0 )) || { echo "usage: $0 <command> [args...]" >&2; exit 2; }

REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

# Remove stale overlay paths inherited from Conda/old colcon workspaces.  ROS
# setup files otherwise try to source a deleted workspace setup.sh.
unset AMENT_PREFIX_PATH COLCON_PREFIX_PATH CMAKE_PREFIX_PATH PYTHONPATH
set +u
source "$ROS_SETUP"
if [[ -f "$REPOSITORY_ROOT/ros2_ws/install/setup.bash" ]]; then
  source "$REPOSITORY_ROOT/ros2_ws/install/setup.bash"
fi
set -u
ROS_PYTHON="${ROS_PYTHON:-/usr/bin/python3}"
[[ -x "$ROS_PYTHON" ]] || { echo "[FATAL] ROS Python is unavailable: $ROS_PYTHON" >&2; exit 2; }
"$ROS_PYTHON" -c 'import rclpy' >/dev/null 2>&1 || { echo "[FATAL] rclpy is unavailable after sourcing ROS" >&2; exit 3; }
exec "$@"
