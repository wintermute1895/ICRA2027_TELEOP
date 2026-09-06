#!/usr/bin/env bash
# Download the frozen low-frequency Qwen visual auditor from an explicit mirror.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/training_env.sh"

ENV_NAME="${VLM_ENV_NAME:-teleop-train}"
MODEL_ID="${QWEN_AUDITOR_MODEL_ID:-Qwen/Qwen2.5-VL-3B-Instruct}"
REVISION="${QWEN_AUDITOR_REVISION:-66285546d2b821cf421d4f5eb2576359d3770cd3}"
HF_ENDPOINT_VALUE="${HF_ENDPOINT:-https://hf-mirror.com}"
EXTERNAL_USER="${SUDO_USER:-${USER:-$(id -un)}}"
DEFAULT_EXTERNAL_CACHE="/media/$EXTERNAL_USER/Cyan_data/ICRA2027_MODELS/huggingface"
if [[ -d "/media/$EXTERNAL_USER/Cyan_data" ]]; then
  DEFAULT_CACHE="$DEFAULT_EXTERNAL_CACHE"
else
  DEFAULT_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/huggingface"
fi
CACHE_ROOT="${VLM_CACHE_DIR:-$DEFAULT_CACHE}"
LOCAL_DIR="${QWEN_AUDITOR_DIR:-$CACHE_ROOT/models/Qwen2.5-VL-3B-Instruct}"

usage() {
  cat >&2 <<'EOF'
Usage: bash scripts/download_qwen_auditor.sh [options]

Options:
  --env-name NAME       Conda environment containing huggingface_hub
  --cache-dir PATH      Hugging Face cache root
  --local-dir PATH      stable model directory
  --hf-endpoint URL     mirror endpoint (default: https://hf-mirror.com)
  --revision COMMIT     immutable model commit

This only downloads and validates model metadata. It does not train, load the
model on GPU, or connect it to robot commands.
EOF
}

while (($#)); do
  case "$1" in
    --env-name) ENV_NAME="${2:-}"; shift 2 ;;
    --cache-dir) CACHE_ROOT="${2:-}"; shift 2 ;;
    --local-dir) LOCAL_DIR="${2:-}"; shift 2 ;;
    --hf-endpoint) HF_ENDPOINT_VALUE="${2:-}"; shift 2 ;;
    --revision) REVISION="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

CONDA_BIN="$(resolve_conda_bin)" || { echo "[FATAL] conda not found" >&2; exit 2; }
PREFIX="$($CONDA_BIN info --base)/envs/$ENV_NAME"
PYTHON="$PREFIX/bin/python"
[[ -x "$PYTHON" ]] || { echo "[FATAL] environment missing: $PREFIX" >&2; exit 2; }
"$PYTHON" -c 'import huggingface_hub' || { echo "[FATAL] huggingface_hub missing in $PREFIX" >&2; exit 2; }
mkdir -p "$CACHE_ROOT" "$LOCAL_DIR"

env HF_ENDPOINT="$HF_ENDPOINT_VALUE" HF_HOME="$CACHE_ROOT" HF_HUB_CACHE="$CACHE_ROOT/hub" \
  "$PYTHON" - "$MODEL_ID" "$REVISION" "$LOCAL_DIR" <<'PY'
import json
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

model_id, revision, local_dir = sys.argv[1:]
resolved = snapshot_download(
    repo_id=model_id,
    revision=revision,
    local_dir=local_dir,
    resume_download=True,
)
root = Path(resolved)
config = json.loads((root / "config.json").read_text(encoding="utf-8"))
if config.get("model_type") not in {"qwen2_5_vl", "qwen2_vl"}:
    raise SystemExit(f"unexpected model_type: {config.get('model_type')}")
files = [path for path in root.rglob("*") if path.is_file()]
size = sum(path.stat().st_size for path in files)
manifest = {
    "schema": "robot_teleop.vlm-model/v0.1",
    "model_id": model_id,
    "revision": revision,
    "resolved_path": str(root.resolve()),
    "model_type": config.get("model_type"),
    "size_bytes": size,
    "role": "offline_low_frequency_visual_auditor",
    "training_policy": "frozen_zero_shot_first",
}
(root / "teleop_model_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2))
PY

echo "[DONE] Qwen auditor cached at: $LOCAL_DIR"
