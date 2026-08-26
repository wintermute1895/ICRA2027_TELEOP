#!/bin/bash
# 构建 arm_teleop ROS2 工作空间（5 个包）：
#   lbot_arm_interfaces / lbot_demo / lbot_driver / lbot_teleop / linkerta
#
# 注意事项：
# - 必须用系统 Python 3.10（/usr/bin/python3）。conda base 的 Python 3.14
#   会让 rosidl_adapter 找不到 empy，构建直接失败。
# - 构建/安装目录必须是纯 ASCII 路径：仓库路径含中文“桌面”，ROS2 的
#   rosidl 生成器会丢掉中文段导致 .idl 路径错误。源码留在仓库没问题。
# - 默认输出到当前用户目录下的 icra2027_teleop_ws（ASCII），可用
#   ARM_TELEOP_WORKSPACE 覆盖。需要干净重编时先删除该目录。
# 注意：不要加 -u。source /opt/ros/humble/setup.bash 会读取未绑定的
# AMENT_TRACE_SETUP_FILES，set -u 会直接中止脚本。
set -eo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARM_SRC="$PROJECT_ROOT/arm_teleop/src"
WS_ROOT="${ARM_TELEOP_WORKSPACE:-$HOME/icra2027_teleop_ws}"

export PATH="/usr/bin:/bin:/usr/local/bin:/usr/sbin:/sbin"
hash -r

if ! command -v ros2 >/dev/null 2>&1; then
  source /opt/ros/humble/setup.bash
fi
if ! command -v colcon >/dev/null 2>&1; then
  echo "[build] colcon not found; install python3-colcon-common-extensions" >&2
  exit 1
fi

echo "[build] python:  $(command -v python3) ($(python3 --version 2>&1))"
echo "[build] source:  $ARM_SRC"
echo "[build] install: $WS_ROOT/install"

mkdir -p "$WS_ROOT"
cd "$WS_ROOT"
colcon build \
  --base-paths "$ARM_SRC" \
  --build-base "$WS_ROOT/build" \
  --install-base "$WS_ROOT/install" \
  --event-handlers console_cohesion+ \
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF

echo "[build] done. Source it with:"
echo "  source $WS_ROOT/install/setup.bash"
