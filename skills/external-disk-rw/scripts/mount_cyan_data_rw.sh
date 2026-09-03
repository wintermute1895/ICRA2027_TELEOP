#!/usr/bin/env bash
set -Eeuo pipefail

# Device names (/dev/sda3, /dev/sdb3, ...) depend on USB enumeration.  The
# filesystem UUID is the disk identity and remains stable across USB ports.
EXPECTED_UUID="${CYAN_DATA_UUID:-3E1D-6B65}"
DEVICE="${CYAN_DATA_DEVICE:-/dev/disk/by-uuid/$EXPECTED_UUID}"
MOUNTPOINT="${CYAN_DATA_MOUNTPOINT:-/media/ilex/Cyan_data}"
USER_ID="${CYAN_DATA_UID:-$(id -u ilex 2>/dev/null || id -u)}"
GROUP_ID="${CYAN_DATA_GID:-$(id -g ilex 2>/dev/null || id -g)}"

[[ -b "$DEVICE" ]] || { echo "[FATAL] Cyan_data disk UUID $EXPECTED_UUID is not connected" >&2; exit 2; }
# /dev/disk/by-uuid is already the kernel-maintained identity assertion. Keep
# its resolved block path for comparison with findmnt without requiring sudo
# every time a training process is started.
DEVICE_CANONICAL="$(readlink -f "$DEVICE")"
mkdir -p "$MOUNTPOINT"

# Systemd automount deliberately creates two stacked records at this path:
# an autofs trigger (SOURCE=systemd-1) and the real exfat filesystem.  Extract
# the latter explicitly; treating the trigger as the disk breaks every normal
# persistent mount.
backing_exfat_record() {
  findmnt -n -M "$MOUNTPOINT" -o SOURCE,FSTYPE,OPTIONS 2>/dev/null \
    | awk '$2 == "exfat" { print $1 "\t" $3; exit }'
}

wait_for_rw_mount() {
  local attempt=1 record options
  while (( attempt <= 10 )); do
    record="$(backing_exfat_record)"
    options="${record#*$'\t'}"
    if [[ -n "$record" ]] && has_option rw "$options"; then
      printf '%s\n' "$record"
      return 0
    fi
    sleep 0.2
    ((attempt++))
  done
  return 1
}

has_option() {
  local needle="$1" options="$2" item
  IFS=',' read -r -a option_items <<< "$options"
  for item in "${option_items[@]}"; do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

# -M checks the mountpoint itself. -T would return the root filesystem when
# the directory merely exists but the external disk is absent.
if findmnt -M "$MOUNTPOINT" >/dev/null 2>&1; then
  # Accessing the directory starts systemd's on-demand mount when only the
  # autofs trigger is present.
  record="$(backing_exfat_record)"
  if [[ -z "$record" ]]; then
    ls -d "$MOUNTPOINT/." >/dev/null 2>&1 || {
      echo "[FATAL] unable to activate Cyan_data automount at $MOUNTPOINT" >&2
      exit 2
    }
    record="$(backing_exfat_record)"
  fi
  [[ -n "$record" ]] || {
    echo "[FATAL] $MOUNTPOINT has an automount trigger but no exFAT backing filesystem" >&2
    exit 2
  }
  source_device="${record%%$'\t'*}"
  options="${record#*$'\t'}"
  [[ "$(readlink -f "$source_device")" == "$DEVICE_CANONICAL" ]] || {
    echo "[FATAL] $MOUNTPOINT is mounted from $source_device, expected Cyan_data UUID $EXPECTED_UUID" >&2
    exit 2
  }
  if wait_for_rw_mount >/dev/null; then
    # Refresh options after the retry; automount can transition between the
    # initial findmnt snapshot and the stable backing mount.
    record="$(backing_exfat_record)"
    options="${record#*$'\t'}"
  fi
  if has_option rw "$options" && has_option "uid=$USER_ID" "$options" && has_option "gid=$GROUP_ID" "$options"; then
    echo "[OK] already mounted read-write: $MOUNTPOINT"
    exit 0
  fi
  echo "[FATAL] Cyan_data is mounted with unexpected options: $options" >&2
  echo "[HINT] Rerun the permanent installer; do not manually remount over systemd automount." >&2
  exit 3
fi

other_target="$(findmnt -rn -S "$(readlink -f "$DEVICE")" -o TARGET | head -n 1 || true)"
[[ -z "$other_target" ]] || {
  echo "[FATAL] Cyan_data is already mounted at $other_target, not $MOUNTPOINT." >&2
  echo "[HINT] Install the permanent UUID automount once: bash scripts/install_cyan_data_automount.sh" >&2
  exit 2
}
sudo mount -t exfat -o "rw,uid=$USER_ID,gid=$GROUP_ID,umask=022" "$DEVICE" "$MOUNTPOINT"
options="$(findmnt -n -M "$MOUNTPOINT" -t exfat -o OPTIONS)"
has_option rw "$options" || { echo "[FATAL] mount did not become read-write: $options" >&2; exit 3; }
test_file="$MOUNTPOINT/.teleop_write_test_$$"
touch "$test_file"
rm -f "$test_file"
echo "[OK] $DEVICE mounted read-write at $MOUNTPOINT (uid=$USER_ID,gid=$GROUP_ID)"
