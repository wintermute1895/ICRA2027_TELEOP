#!/usr/bin/env bash
# Recreate the ICRA2027_TELEOP software stack on Ubuntu 22.04 x86_64.
#
# Usage:
#   bash scripts/bootstrap_new_machine.sh
#   TORCH_VARIANT=cpu bash scripts/bootstrap_new_machine.sh
#   bash scripts/bootstrap_new_machine.sh --skip-ros

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${ENV_NAME:-dex_teleop}"
TORCH_VARIANT="${TORCH_VARIANT:-auto}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
INSTALL_ROS=1
THIRD_PARTY_ROOT="$PROJECT_ROOT/.bootstrap-third-party"

for bootstrap_arg in "$@"; do
    case "$bootstrap_arg" in
        --skip-ros) INSTALL_ROS=0 ;;
        *) echo "Unknown argument: $bootstrap_arg" >&2; exit 2 ;;
    esac
done

fail() {
    echo "[bootstrap] $*" >&2
    exit 1
}

require_ubuntu_2204() {
    [[ -r /etc/os-release ]] || fail "This installer requires Ubuntu 22.04."
    # shellcheck disable=SC1091
    source /etc/os-release
    [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "22.04" ]] || \
        fail "ROS Humble reproduction is supported only on Ubuntu 22.04."
    [[ "$(uname -m)" == "x86_64" ]] || fail "Only x86_64 is supported."
}

install_system_packages() {
    sudo apt-get update
    sudo apt-get install -y \
        ca-certificates curl git build-essential ffmpeg \
        libgl1 libglib2.0-0 libusb-1.0-0 libportaudio2 \
        python3-tk can-utils software-properties-common
}

install_ros_humble() {
    if [[ ! -f /opt/ros/humble/setup.bash ]]; then
        sudo add-apt-repository -y universe
        sudo curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
            -o /usr/share/keyrings/ros-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
            | sudo tee /etc/apt/sources.list.d/ros2.list >/dev/null
        sudo apt-get update
    fi

    sudo apt-get install -y \
        ros-humble-desktop ros-humble-realsense2-camera \
        python3-colcon-common-extensions python3-rosdep python3-vcstool
    sudo rosdep init 2>/dev/null || true
    rosdep update
}

install_miniforge_if_needed() {
    if command -v conda >/dev/null 2>&1; then
        CONDA_EXE="$(command -v conda)"
        return
    fi

    local conda_root="${CONDA_ROOT:-$HOME/miniforge3}"
    if [[ ! -x "$conda_root/bin/conda" ]]; then
        local installer="/tmp/Miniforge3-Linux-x86_64.sh"
        curl -fsSL \
            https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh \
            -o "$installer"
        bash "$installer" -b -p "$conda_root"
        rm -f "$installer"
    fi
    CONDA_EXE="$conda_root/bin/conda"
}

select_torch_index() {
    if [[ "$TORCH_VARIANT" == "auto" ]]; then
        if command -v nvidia-smi >/dev/null 2>&1; then
            TORCH_VARIANT="cu126"
        else
            TORCH_VARIANT="cpu"
        fi
    fi

    case "$TORCH_VARIANT" in
        cu126) TORCH_INDEX_URL="https://download.pytorch.org/whl/cu126" ;;
        cpu) TORCH_INDEX_URL="https://download.pytorch.org/whl/cpu" ;;
        *) fail "TORCH_VARIANT must be cu126, cpu, or auto." ;;
    esac
}

prepare_checkout() {
    local checkout_name="$1"
    local remote_url="$2"
    local revision="$3"
    local patch_file="$4"
    local checkout_path="$THIRD_PARTY_ROOT/$checkout_name"

    if [[ ! -d "$checkout_path/.git" ]]; then
        git clone "$remote_url" "$checkout_path" >&2
    fi
    git -C "$checkout_path" fetch --tags origin >&2
    git -C "$checkout_path" checkout --detach "$revision" >&2
    git -C "$checkout_path" reset --hard "$revision" >&2
    git -C "$checkout_path" clean -fdx >&2
    git -C "$checkout_path" apply --check "$patch_file" >&2
    git -C "$checkout_path" apply "$patch_file" >&2
    printf '%s\n' "$checkout_path"
}

install_conda_environment() {
    if ! "$CONDA_EXE" run -n "$ENV_NAME" python -c 'import sys; assert sys.version_info[:2] == (3, 10)' >/dev/null 2>&1; then
        "$CONDA_EXE" create -y --override-channels -c conda-forge \
            -n "$ENV_NAME" python=3.10 pip pinocchio=3.7.0 portaudio
    fi

    local env_python
    env_python="$($CONDA_EXE run -n "$ENV_NAME" python -c 'import sys; print(sys.executable)')"
    PYTHONNOUSERSITE=1 "$env_python" -m pip install --upgrade pip
    PYTHONNOUSERSITE=1 "$env_python" -m pip install \
        --index-url "$TORCH_INDEX_URL" \
        "torch==2.6.0+$TORCH_VARIANT" \
        "torchvision==0.21.0+$TORCH_VARIANT" \
        "torchaudio==2.6.0+$TORCH_VARIANT"
    PYTHONNOUSERSITE=1 "$env_python" -m pip install \
        --index-url "$PIP_INDEX_URL" \
        -r "$PROJECT_ROOT/requirements/dex_teleop.txt"
    # These packages use the PyPI distribution name "pin".  Pinocchio is
    # already installed by Conda, so do not allow pip to install a duplicate.
    PYTHONNOUSERSITE=1 "$env_python" -m pip install --no-deps \
        --index-url "$PIP_INDEX_URL" pin-pink==3.1.0 dex-retargeting==0.4.6

    mkdir -p "$THIRD_PARTY_ROOT"
    local dexmimicgen_path robosuite_path
    dexmimicgen_path="$(prepare_checkout \
        dexmimicgen \
        https://gitee.com/mirrors_NVlabs/dexmimicgen.git \
        940e8a1b3ad70eb1925ada6b364b197de6bb2af9 \
        "$PROJECT_ROOT/third_party_patches/dexmimicgen-packaging.patch")"
    robosuite_path="$(prepare_checkout \
        robosuite \
        https://gitee.com/mirrors_ARISE-Initiative/robosuite.git \
        1a8701b90c07c6595ace4af9935d7c5ebe1baed3 \
        "$PROJECT_ROOT/third_party_patches/robosuite-packaging-and-mink.patch")"
    PYTHONNOUSERSITE=1 "$env_python" -m pip install --no-deps --force-reinstall \
        "$dexmimicgen_path" "$robosuite_path"
}

verify_conda_environment() {
    local env_python
    env_python="$($CONDA_EXE run -n "$ENV_NAME" python -c 'import sys; print(sys.executable)')"
    PYTHONNOUSERSITE=1 MPLCONFIGDIR=/tmp/icra2027_mpl \
        NUMBA_CACHE_DIR=/tmp/icra2027_numba "$env_python" -c '
import dexmimicgen, lerobot, mediapipe, mujoco, pinocchio, pink, pyrealsense2, robosuite, torch
from dex_retargeting.retargeting_config import RetargetingConfig
from robosuite.examples.third_party_controller.mink_controller import WholeBodyMinkIK
print("[verify] Conda runtime imports OK")
'
    PYTHONNOUSERSITE=1 MPLCONFIGDIR=/tmp/icra2027_mpl \
        NUMBA_CACHE_DIR=/tmp/icra2027_numba "$env_python" \
        "$PROJECT_ROOT/dexmimicgen_lerobot_validation/scripts/rollout_act_robosuite.py" --help >/dev/null
    PYTHONNOUSERSITE=1 "$env_python" "$PROJECT_ROOT/IROS_teleop/check.py" >/dev/null
}

build_and_verify_ros() {
    # shellcheck disable=SC1091
    source /opt/ros/humble/setup.bash
    rosdep install --from-paths "$PROJECT_ROOT/arm_teleop/src" --ignore-src -r -y
    ARM_TELEOP_WORKSPACE="${ARM_TELEOP_WORKSPACE:-$HOME/icra2027_teleop_ws}" \
        bash "$PROJECT_ROOT/scripts/build_arm_teleop.sh"
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/scripts/d0_env.sh"
    /usr/bin/python3 -c 'import rclpy, rosbag2_py, rosidl_runtime_py; print("[verify] ROS runtime imports OK")'
}

main() {
    require_ubuntu_2204
    install_system_packages
    install_miniforge_if_needed
    select_torch_index
    install_conda_environment
    verify_conda_environment
    if [[ "$INSTALL_ROS" == 1 ]]; then
        install_ros_humble
        build_and_verify_ros
    fi
    cat <<EOF
[bootstrap] Complete.
  Conda runtime: conda activate $ENV_NAME
  ROS runtime:   source scripts/d0_env.sh
EOF
}

main
