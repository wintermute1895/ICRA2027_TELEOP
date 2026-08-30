#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" != "--clean-env" ]]; then
  exec env -u CONDA_PREFIX -u CONDA_DEFAULT_ENV -u PYTHONPATH -u LD_LIBRARY_PATH \
    PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" bash "$0" --clean-env
fi
ROS_SETUP=""
for distro in "${ROS_DISTRO:-}" jazzy humble; do
  [[ -n "$distro" && -f "/opt/ros/$distro/setup.bash" ]] || continue
  ROS_SETUP="/opt/ros/$distro/setup.bash"
  break
done
[[ -n "$ROS_SETUP" ]] || { echo "no supported ROS2 setup found under /opt/ros" >&2; exit 2; }
set +u
source "$ROS_SETUP"
set -u
# This host can have an unrelated user-managed Python 3.10.  Jazzy's generated
# interfaces must use Ubuntu's Python 3.12, so do not let CMake auto-discover
# the incompatible interpreter from ~/.local.
colcon --log-base "${ROOT_DIR}/ros2_ws/log" build --base-paths "${ROOT_DIR}/ros2_ws/src" --build-base "${ROOT_DIR}/ros2_ws/build" --install-base "${ROOT_DIR}/ros2_ws/install" --symlink-install --cmake-clean-cache --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3 -DPYTHON_EXECUTABLE=/usr/bin/python3
