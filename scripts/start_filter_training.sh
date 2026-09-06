#!/usr/bin/env bash
# Single safe entry point for GPU filter rounds stored on Cyan_data.
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-$ROOT_DIR/config/filters/coldstart_episode1_vlm_v1.yaml}"
[[ -f "$CONFIG" ]] || { echo "[FATAL] round config not found: $CONFIG" >&2; exit 2; }

# The helper verifies the Cyan_data filesystem UUID, so a local directory with
# the same name can never silently receive captures or model outputs.
bash "$ROOT_DIR/skills/external-disk-rw/scripts/mount_cyan_data_rw.sh"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/lib/training_env.sh"
ENV_PREFIX="$(resolve_training_env_prefix)" || { echo "[FATAL] teleop-train environment is unavailable" >&2; exit 2; }
exec env PYTHONPATH="$ROOT_DIR/src" "$ENV_PREFIX/bin/python" "$ROOT_DIR/tools/run_filter_round.py" --config "$CONFIG"
