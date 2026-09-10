#!/usr/bin/env bash
# Resolve the active data-disk root for deployment/training paths.
#
# Priority:
#   1. $TELEOP_DATA_ROOT (explicit override always wins)
#   2. First mounted candidate below (fixed order avoids ambiguity when
#      several disks are mounted at once)
#
# The mount point may change between sessions; the layout BELOW the root
# (ICRA2027_Data/...) is the stable contract.
#
# Usage:
#   scripts/resolve_data_disk.sh                  # print resolved root, exit 2 if none
#   scripts/resolve_data_disk.sh --require rel/a  # also verify rel/a exists under root
set -Eeuo pipefail

USER_NAME="${USER:-$(id -un)}"
CANDIDATES=(
  "/media/${USER_NAME}/robot_data/ICRA2027_Data"
  "/media/${USER_NAME}/Cyan_data/ICRA2027_DATA"
  "/media/${USER_NAME}/Seagate Hub/ICRA2027"
)

ROOT=""
if [[ -n "${TELEOP_DATA_ROOT:-}" && -d "${TELEOP_DATA_ROOT}" ]]; then
  ROOT="${TELEOP_DATA_ROOT}"
else
  for candidate in "${CANDIDATES[@]}"; do
    if [[ -d "$candidate" ]]; then
      ROOT="$candidate"
      break
    fi
  done
fi

if [[ -z "$ROOT" ]]; then
  echo "[FATAL] no data disk found. Checked:" >&2
  printf '  %s\n' "${CANDIDATES[@]}" >&2
  echo "Set TELEOP_DATA_ROOT explicitly to override." >&2
  exit 2
fi

while (($#)); do
  case "$1" in
    --require)
      REL="${2:-}"; shift 2
      if [[ ! -e "$ROOT/$REL" ]]; then
        echo "[FATAL] required path missing under $ROOT: $REL" >&2
        exit 2
      fi
      ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

echo "$ROOT"
