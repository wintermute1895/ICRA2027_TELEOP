#!/usr/bin/env bash
# Provision an isolated local VLM environment and optionally cache weights.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/training_env.sh"
ENV_NAME="${VLM_ENV_NAME:-teleop-train}"
MODEL_ID="${VLM_MODEL_ID:-google/siglip2-base-patch16-224}"
MODEL_REVISION="${VLM_MODEL_REVISION:-main}"
DEFAULT_SIGLIP_CACHE="/media/${USER:-$(id -un)}/Cyan_data/ICRA2027_MODELS/huggingface"
if [[ -d "/media/${USER:-$(id -un)}/Seagate Hub/ICRA2027_DATA_TASK2" ]]; then
  DEFAULT_VLM_CACHE="$DEFAULT_SIGLIP_CACHE"
else
  DEFAULT_VLM_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/huggingface"
fi
HF_CACHE="${VLM_CACHE_DIR:-$DEFAULT_VLM_CACHE}"
HF_ENDPOINT_VALUE="${HF_ENDPOINT:-}"
PYTHON_VERSION="${VLM_PYTHON_VERSION:-3.11}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
DOWNLOAD=0

usage() {
  cat >&2 <<'EOF'
Usage: bash scripts/install_vlm.sh [options]

Options:
  --env-name NAME       Conda environment (default: teleop-train; override for isolation)
  --model-id ID         Hugging Face model (default: google/siglip2-base-patch16-224)
  --revision REV        Model revision/commit (default: main)
  --cache-dir PATH      Hugging Face cache (default: ~/.cache/huggingface)
  --hf-endpoint URL     Hugging Face endpoint/mirror for this download only
  --download            Download processor and weights now

Set HF_ENDPOINT explicitly when using an approved mirror. No credentials or
tokens are written to the repository.
EOF
}

while (($#)); do
  case "$1" in
    --env-name) ENV_NAME="${2:-}"; shift 2 ;;
    --model-id) MODEL_ID="${2:-}"; shift 2 ;;
    --revision) MODEL_REVISION="${2:-}"; shift 2 ;;
    --cache-dir) HF_CACHE="${2:-}"; shift 2 ;;
    --hf-endpoint) HF_ENDPOINT_VALUE="${2:-}"; shift 2 ;;
    --download) DOWNLOAD=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

CONDA_BIN="$(resolve_conda_bin)" || { echo "[FATAL] conda not found" >&2; exit 2; }
BASE="$($CONDA_BIN info --base)"
PREFIX="$BASE/envs/$ENV_NAME"
if [[ ! -x "$PREFIX/bin/python" ]]; then
  "$CONDA_BIN" create -y -n "$ENV_NAME" "python=$PYTHON_VERSION" pip
fi
if ! "$PREFIX/bin/python" -c 'import torch' >/dev/null 2>&1; then
  echo "[INFO] installing PyTorch because the selected environment lacks it"
  "$PREFIX/bin/python" -m pip install torch -i "$PIP_INDEX_URL"
fi
"$PREFIX/bin/python" -m pip install --upgrade pip -i "$PIP_INDEX_URL"
"$PREFIX/bin/python" -m pip install -r "$ROOT_DIR/requirements-vlm.txt" -i "$PIP_INDEX_URL"

mkdir -p "$HF_CACHE"
if ((DOWNLOAD)); then
  # Keep the cache layout stable when CACHE_DIR is an external data disk.
  download_env=(env "HF_HOME=$HF_CACHE" "HF_HUB_CACHE=$HF_CACHE")
  if [[ -n "$HF_ENDPOINT_VALUE" ]]; then
    download_env+=("HF_ENDPOINT=$HF_ENDPOINT_VALUE")
  fi
  "${download_env[@]}" "$PREFIX/bin/python" - "$MODEL_ID" "$MODEL_REVISION" <<'PY'
import sys
from transformers import AutoModel, AutoProcessor

model_id, revision = sys.argv[1:]
AutoProcessor.from_pretrained(model_id, revision=revision)
AutoModel.from_pretrained(model_id, revision=revision)
print(f"cached model: {model_id}@{revision}")
PY
fi

cat <<EOF
[DONE] VLM environment: $PREFIX
[DONE] model: $MODEL_ID@$MODEL_REVISION
[DONE] HF cache: $HF_CACHE
EOF
if [[ -n "$HF_ENDPOINT_VALUE" ]]; then
  printf '[DONE] HF endpoint: %s\n' "$HF_ENDPOINT_VALUE"
fi
