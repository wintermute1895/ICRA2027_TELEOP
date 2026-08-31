#!/usr/bin/env bash
set -euo pipefail

# Run the independent f-key hand controller. This script starts no SDK and no
# recorder; launch hand_interface.py separately with the required safety gate.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEM_PYTHON="${SYSTEM_PYTHON:-/usr/bin/python3}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
WORKSPACE_SETUP="${WORKSPACE_SETUP:-${ROOT_DIR}/ros2_ws/install/setup.bash}"
set +u
if [[ -f "$ROS_SETUP" ]]; then
  # shellcheck disable=SC1090
  source "$ROS_SETUP"
fi
if [[ -f "$WORKSPACE_SETUP" ]]; then
  # shellcheck disable=SC1090
  source "$WORKSPACE_SETUP"
fi
set -u
exec "$SYSTEM_PYTHON" "$ROOT_DIR/tools/hand_preset_controller.py" \
  --config "${HAND_PRESET_CONFIG:-$ROOT_DIR/config/hand_presets.json}" "$@"
