#!/usr/bin/env bash
# Run the simulation node with the project-owned Python 3.10 MuJoCo runtime.
set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MPC_PYTHON="${MPC_PYTHON:-/home/ilex/miniforge3/envs/mpc_env/bin/python}"

if [[ ! -x "$MPC_PYTHON" ]]; then
  echo "[FATAL] MuJoCo Python not found: $MPC_PYTHON" >&2
  exit 2
fi

source /opt/ros/humble/setup.bash
source "$ROOT/ros2_ws/install/setup.bash"
set -u
exec "$MPC_PYTHON" "$ROOT/ros2_ws/install/sim_robot_driver/lib/sim_robot_driver/mujoco_command_mirror" "$@"
