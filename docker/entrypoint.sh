#!/usr/bin/env bash
set -euo pipefail
source /opt/ros/humble/setup.bash
source /opt/icra2027_teleop/arm_teleop/install/setup.bash
exec "$@"
