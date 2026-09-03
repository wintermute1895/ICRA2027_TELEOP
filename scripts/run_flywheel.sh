#!/usr/bin/env bash
# Stable capture-to-training entry point. All settings live in one YAML file.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${1:-}"
CONFIG="${2:-$ROOT_DIR/config/flywheel/default.yaml}"

if [[ "$SOURCE" == "-h" || "$SOURCE" == "--help" ]]; then
  echo "Usage: bash scripts/run_flywheel.sh CAPTURE_RUN_OR_ROSBAG [CONFIG]"
  exit 0
fi
if [[ -z "$SOURCE" ]]; then
  echo "Usage: bash scripts/run_flywheel.sh CAPTURE_RUN_OR_ROSBAG [CONFIG]" >&2
  exit 2
fi

bash "$ROOT_DIR/skills/external-disk-rw/scripts/mount_cyan_data_rw.sh"
source "$ROOT_DIR/scripts/lib/training_env.sh"
ENV_PREFIX="$(resolve_training_env_prefix)" || {
  echo "[FATAL] teleop-train environment is unavailable" >&2
  exit 2
}

exec env PYTHONPATH="$ROOT_DIR/src" "$ENV_PREFIX/bin/python" \
  "$ROOT_DIR/tools/run_flywheel.py" "$SOURCE" --config "$CONFIG"
