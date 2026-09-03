#!/usr/bin/env bash
# Install a UUID-based, on-demand writable mount for the project data disk.
set -Eeuo pipefail

EXPECTED_UUID="${CYAN_DATA_UUID:-3E1D-6B65}"
DEVICE="${CYAN_DATA_DEVICE:-/dev/disk/by-uuid/$EXPECTED_UUID}"
MOUNTPOINT="${CYAN_DATA_MOUNTPOINT:-/media/ilex/Cyan_data}"
USER_ID="${CYAN_DATA_UID:-$(id -u)}"
GROUP_ID="${CYAN_DATA_GID:-$(id -g)}"
[[ -b "$DEVICE" ]] || { echo "[FATAL] Cyan_data disk UUID $EXPECTED_UUID is not connected" >&2; exit 2; }
# Read raw block metadata with sudo: on this host ordinary users may list the
# disk but cannot query its UUID with blkid.
UUID="$(sudo blkid -s UUID -o value "$DEVICE" 2>/dev/null || true)"
FSTYPE="$(sudo blkid -s TYPE -o value "$DEVICE" 2>/dev/null || true)"
[[ "$UUID" == "$EXPECTED_UUID" && "$FSTYPE" == exfat ]] || {
  echo "[FATAL] expected Cyan_data exFAT UUID $EXPECTED_UUID, got ${UUID:-unknown} ($FSTYPE)" >&2
  exit 2
}

line="UUID=$UUID $MOUNTPOINT exfat defaults,uid=$USER_ID,gid=$GROUP_ID,umask=022,nofail,x-systemd.automount,x-systemd.device-timeout=1s 0 0"
if grep -Eq "^[^#].*[[:space:]]$MOUNTPOINT[[:space:]]" /etc/fstab; then
  existing="$(grep -E "^[^#].*[[:space:]]$MOUNTPOINT[[:space:]]" /etc/fstab)"
  [[ "$existing" == "$line" ]] || { echo "[FATAL] $MOUNTPOINT already has a different /etc/fstab entry:" >&2; echo "$existing" >&2; exit 3; }
  echo "[OK] automount entry already installed"
else
  echo "[INFO] installing UUID-based automount for $DEVICE ($UUID)"
  sudo cp /etc/fstab "/etc/fstab.backup.$(date +%Y%m%dT%H%M%S)"
  printf '%s\n' "$line" | sudo tee -a /etc/fstab >/dev/null
fi
sudo mkdir -p "$MOUNTPOINT"
# Desktop automounters may have mounted this UUID at Cyan_data1.  Unmount every
# existing mount of this exact filesystem so fstab owns the one canonical path.
while IFS= read -r target; do
  [[ -z "$target" ]] || sudo umount "$target"
done < <(findmnt -rn -S "$(readlink -f "$DEVICE")" -o TARGET || true)
if findmnt -M "$MOUNTPOINT" >/dev/null 2>&1; then sudo umount "$MOUNTPOINT"; fi
sudo systemctl daemon-reload
sudo systemctl start "$(systemd-escape -p --suffix=automount "$MOUNTPOINT")"
# Trigger the automount and prove that the current user can write.
test_file="$MOUNTPOINT/.teleop_automount_test_$$"
touch "$test_file"
rm -f "$test_file"
findmnt -M "$MOUNTPOINT" -o SOURCE,TARGET,FSTYPE,OPTIONS
echo "[OK] persistent automount installed; USB port changes do not affect UUID matching"
