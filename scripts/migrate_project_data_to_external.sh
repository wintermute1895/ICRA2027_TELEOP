#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTERNAL_ROOT="${1:-/media/ilex/Cyan_data/ICRA2027_TELEOP_DATA}"
DELETE_SOURCE=0
[[ "${2:-}" == "--delete-source" ]] && DELETE_SOURCE=1

findmnt -T "$(dirname "$EXTERNAL_ROOT")" >/dev/null 2>&1 || { echo "[FATAL] external disk is not mounted: $EXTERNAL_ROOT" >&2; exit 2; }
mount_options="$(findmnt -n -T "$(dirname "$EXTERNAL_ROOT")" -o OPTIONS)"
[[ "$mount_options" == *rw* ]] || { echo "[FATAL] external disk is read-only; run the external-disk-rw skill first" >&2; exit 2; }
mkdir -p "$EXTERNAL_ROOT"
[[ -w "$EXTERNAL_ROOT" ]] || { echo "[FATAL] external destination is not writable: $EXTERNAL_ROOT" >&2; exit 2; }

for source in evidence reports gestures runs derived; do
  [[ -d "$ROOT_DIR/$source" ]] || continue
  destination="$EXTERNAL_ROOT/$source"
  mkdir -p "$destination"
  echo "[COPY] $source -> $destination"
  # exFAT has no Unix ownership, mode bits, or symlinks. Skip the one
  # generated absolute ros-log link; its target directory is copied normally.
  rsync -rlt --no-perms --no-owner --no-group --exclude='teleop/system/ros_logs/latest' --human-readable --info=progress2 "$ROOT_DIR/$source/" "$destination/"
  echo "[VERIFY] checksumming regular files for $source (may take a few minutes)"
  src_sum="$(cd "$ROOT_DIR/$source" && find -type f -printf '%P\n' -exec sha256sum {} \; | sort | sha256sum | awk '{print $1}')"
  dst_sum="$(cd "$destination" && find -type f -printf '%P\n' -exec sha256sum {} \; | sort | sha256sum | awk '{print $1}')"
  [[ "$src_sum" == "$dst_sum" ]] || { echo "[FATAL] checksum mismatch for $source" >&2; exit 3; }
  echo "[OK] verified $source"
  if (( DELETE_SOURCE )); then
    echo "[REMOVE] deleting verified source $ROOT_DIR/$source"
    rm -rf -- "$ROOT_DIR/$source"
  fi
done
echo "[DONE] external data root: $EXTERNAL_ROOT"
if (( ! DELETE_SOURCE )); then echo "[INFO] source retained; rerun with --delete-source after inspection"; fi
