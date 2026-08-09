#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" != "--clean-env" ]]; then
  exec env -u CONDA_PREFIX -u CONDA_DEFAULT_ENV -u PYTHONPATH -u LD_LIBRARY_PATH \
    PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" bash "$0" --clean-env
fi
if [[ ! -f /opt/ros/humble/setup.bash ]]; then echo "ROS2 Humble not found" >&2; exit 2; fi
set +u
source /opt/ros/humble/setup.bash
set -u
colcon --log-base "${ROOT_DIR}/arm_teleop/log" build --base-paths "${ROOT_DIR}/arm_teleop/src" --build-base "${ROOT_DIR}/arm_teleop/build" --install-base "${ROOT_DIR}/arm_teleop/install" --symlink-install
