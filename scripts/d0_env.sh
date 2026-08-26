#!/bin/bash
# D0 遥操录包环境。
#
# - 强制使用系统 Python 3.10：conda base（3.14）会让 ros2/rosidl 失败
#   （缺少 empy），dex_teleop 的 Python 也缺 empy。
# - arm_teleop 默认指向当前用户目录下的 ASCII 工作空间
#   （由 scripts/build_arm_teleop.sh 构建）。仓库路径含中文，不能作为
#   ROS2 构建/安装目录。可用 ARM_TELEOP_WORKSPACE 覆盖。
ARM_TELEOP_WORKSPACE="${ARM_TELEOP_WORKSPACE:-$HOME/icra2027_teleop_ws}"

export PATH="/usr/bin:/bin:/usr/local/bin:/usr/sbin:/sbin:$PATH"
hash -r

source /opt/ros/humble/setup.bash
source "$ARM_TELEOP_WORKSPACE/install/setup.bash"
export ROS_DOMAIN_ID=77
export ROS_LOCALHOST_ONLY=1
