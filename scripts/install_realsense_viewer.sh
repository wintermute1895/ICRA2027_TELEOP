#!/usr/bin/env bash
# Install Intel RealSense Viewer and its official runtime repository.
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with: sudo bash scripts/install_realsense_viewer.sh" >&2
  exit 1
fi

command -v curl >/dev/null || { echo "curl is required" >&2; exit 2; }
command -v gpg >/dev/null || { echo "gpg is required" >&2; exit 2; }

keyring='/etc/apt/keyrings/librealsense.pgp'
source_file='/etc/apt/sources.list.d/librealsense.list'
key_url='https://keyserver.ubuntu.com/pks/lookup?op=get&search=0xFB0B24895113F120'
expected_fingerprint='5381411D24E659FB18195FA5FB0B24895113F120'

install -d -m 0755 /etc/apt/keyrings
tmp_key="$(mktemp)"
trap 'rm -f "$tmp_key"' EXIT

echo '[1/4] Downloading Intel RealSense repository key'
curl --fail --silent --show-error --location \
  "$key_url" \
  | gpg --dearmor >"$tmp_key"
gpg --show-keys --with-colons "$tmp_key" | grep -Fq "fpr:::::::::${expected_fingerprint}:" \
  || { echo "Downloaded key does not match expected RealSense signing key." >&2; exit 1; }
install -m 0644 "$tmp_key" "$keyring"

echo '[2/4] Configuring Intel RealSense repository'
cat >"$source_file" <<'EOF'
deb [signed-by=/etc/apt/keyrings/librealsense.pgp] https://librealsense.intel.com/Debian/apt-repo noble main
EOF

echo '[3/4] Refreshing APT metadata'
apt-get update

echo '[4/4] Installing RealSense Viewer'
apt-get install -y librealsense2-utils

echo
echo 'Installed. Start the GUI with: realsense-viewer'
