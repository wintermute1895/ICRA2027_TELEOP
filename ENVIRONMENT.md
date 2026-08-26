# ICRA2027_TELEOP runtime environments

## New machine bootstrap

On a clean Ubuntu 22.04 x86_64 machine with internet access, clone this
repository and run the following once. The command installs Miniforge when
needed, creates the Conda environment, installs the pinned Python stack,
fetches the pinned ACT simulation sources, installs ROS Humble, builds the ROS
overlay, and runs import checks. It prompts for `sudo` when system packages are
needed.

```bash
bash scripts/bootstrap_new_machine.sh
```

The default GPU build is CUDA 12.6 when `nvidia-smi` is present; it otherwise
uses CPU PyTorch. Set `TORCH_VARIANT=cpu` explicitly to force CPU mode. Use
`--skip-ros` for an ACT-only computer.

The full path requires an NVIDIA driver compatible with CUDA 12.6 for GPU
training, plus a RealSense camera and CAN adapter only when those hardware
workflows are used. The installer validates imports and ROS interfaces; it
does not attempt to move real hardware.

This project intentionally uses two isolated Python runtimes.  Do not mix
their package installations.

## ACT, simulation, vision, IK, and direct hand tools

Use the dedicated Conda environment:

```bash
conda activate dex_teleop
export PYTHONNOUSERSITE=1
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/icra2027_mpl}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/icra2027_numba}"
```

The environment is Python 3.10 and contains the validated ACT / LeRobot,
DexMimicGen / Robosuite, MuJoCo, Pinocchio, Pink, dex-retargeting,
MediaPipe, RealSense, Meshcat, CAN, and audio dependencies.  The simulation
packages are installed as ordinary packages in this Conda environment, rather
than editable imports from another workspace.

Quick checks:

```bash
PYTHONNOUSERSITE=1 python dexmimicgen_lerobot_validation/scripts/convert_robomimic_to_lerobot.py --help
PYTHONNOUSERSITE=1 python dexmimicgen_lerobot_validation/scripts/rollout_act_robosuite.py --help
PYTHONNOUSERSITE=1 python IROS_teleop/check.py
```

## ROS 2 recording and robot driver

ROS Humble packages (`rclpy`, `rosbag2_py`, generated message modules, and
`colcon`) are system / apt packages tied to `/usr/bin/python3` and `/opt/ros`.
They must not be installed with pip into `dex_teleop`.  Use the existing setup
script, which selects the system Python and the ASCII-only ROS workspace:

```bash
source scripts/d0_env.sh
/usr/bin/python3 scripts/d0_split.py --help
```

Before building the ROS workspace, leave Conda deactivated and run
`scripts/build_arm_teleop.sh`.
