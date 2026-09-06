#!/usr/bin/env bash
set -euo pipefail
source /opt/ros/humble/setup.bash
source /opt/robot_teleop_platform/ros2_ws/install/setup.bash
exec "$@"
