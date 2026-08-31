#!/usr/bin/env bash
# Configure direct domestic APT mirrors for Ubuntu 24.04 and ROS 2 Jazzy.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with: sudo bash scripts/configure_tuna_apt_sources.sh" >&2
  exit 1
fi

ubuntu_source="/etc/apt/sources.list.d/ubuntu.sources"
ros_source="/etc/apt/sources.list.d/ros2.list"
timestamp="$(date +%Y%m%d_%H%M%S)"

for source_file in "${ubuntu_source}" "${ros_source}"; do
  if [[ ! -f "${source_file}" ]]; then
    echo "Expected source file is missing: ${source_file}" >&2
    exit 1
  fi
done

for source_file in "${ubuntu_source}" "${ros_source}"; do
  backup="${source_file}.before-tuna-${timestamp}.bak"
  cp --preserve=mode,ownership,timestamps "${source_file}" "${backup}"
  echo "Backed up ${source_file} to ${backup}"
done

cat >"${ubuntu_source}" <<'EOF'
Types: deb
URIs: https://mirrors.tuna.tsinghua.edu.cn/ubuntu/
Suites: noble noble-updates noble-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: https://mirrors.tuna.tsinghua.edu.cn/ubuntu/
Suites: noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF

cat >"${ros_source}" <<'EOF'
deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] https://mirrors.tuna.tsinghua.edu.cn/ros2/ubuntu noble main
EOF

apt-get update

echo "APT now uses TUNA directly for Ubuntu and ROS 2."
echo "To revert, restore the two .before-tuna-${timestamp}.bak files and run apt-get update."
