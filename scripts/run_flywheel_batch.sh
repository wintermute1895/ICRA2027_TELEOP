#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${ROOT_DIR}/config/flywheel/default.yaml"
LIMIT=0
PREPARE_ONLY=0
while (($#)); do
  case "$1" in
    --config) CONFIG="${2:-}"; shift 2 ;;
    --limit) LIMIT="${2:-}"; shift 2 ;;
    --prepare-only) PREPARE_ONLY=1; shift ;;
    -h|--help)
      echo "Usage: bash scripts/run_flywheel_batch.sh [--config PATH] [--limit N] [--prepare-only]"
      exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

bash "$ROOT_DIR/skills/external-disk-rw/scripts/mount_cyan_data_rw.sh"
source "$ROOT_DIR/scripts/lib/training_env.sh"
ENV_PREFIX="$(resolve_training_env_prefix)" || { echo "[FATAL] teleop-train environment is unavailable" >&2; exit 2; }
ARGS=("$ROOT_DIR/tools/run_flywheel_batch.py" --config "$CONFIG" --limit "$LIMIT")
(( PREPARE_ONLY )) && ARGS+=(--prepare-only)
exec env PYTHONPATH="$ROOT_DIR/src" "$ENV_PREFIX/bin/python" "${ARGS[@]}"
