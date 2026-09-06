#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REAL=0
CONFIRM=""
for arg in "$@"; do
  case "$arg" in
    --real) REAL=1 ;;
    --confirm=*) CONFIRM="${arg#*=}" ;;
    *) echo "usage: $0 [--real --confirm=I_UNDERSTAND_REAL_ROBOT]" >&2; exit 2 ;;
  esac
done
if [[ ! -f /opt/ros/humble/setup.bash ]]; then echo "ROS2 Humble not found" >&2; exit 2; fi
set +u
source /opt/ros/humble/setup.bash
set -u
if [[ ! -f "${ROOT_DIR}/ros2_ws/install/setup.bash" ]]; then
  echo "ROS2 workspace is not built. Run scripts/build_ros2_workspace.sh first." >&2; exit 2
fi
set +u
source "${ROOT_DIR}/ros2_ws/install/setup.bash"
set -u
if (( ! REAL )); then
  echo "Preflight only. No real robot launch requested."
  python3 "${ROOT_DIR}/scripts/preflight.py" --mode ros2 || true
  exit 0
fi
if [[ "${CONFIRM}" != "I_UNDERSTAND_REAL_ROBOT" ]]; then
  echo "Refusing real-robot launch: pass --confirm=I_UNDERSTAND_REAL_ROBOT" >&2; exit 3
fi
python3 "${ROOT_DIR}/scripts/preflight.py" --mode ros2
echo "Launching ROS2 real-robot teleoperation. Keep the physical emergency stop reachable."
exec ros2 launch teleop_control_bridge hardware_teleop.launch.py armed:=true
