#!/usr/bin/env bash
# Build a frozen multi-camera VLM view for an admitted residual-training episode.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/training_env.sh"

EPISODE=""
OUTPUT_DIR=""
MODEL_ID="${VLM_MODEL_ID:-google/siglip2-base-patch16-224}"
REVISION="${VLM_MODEL_REVISION:-main}"
DEFAULT_SIGLIP_CACHE="/media/${USER:-$(id -un)}/Seagate Hub/ICRA2027_DATA_TASK2/vlm_cache"
if [[ -d "/media/${USER:-$(id -un)}/Seagate Hub/ICRA2027_DATA_TASK2" ]]; then
  DEFAULT_VLM_CACHE="$DEFAULT_SIGLIP_CACHE"
else
  DEFAULT_VLM_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/huggingface"
fi
CACHE_DIR="${VLM_CACHE_DIR:-$DEFAULT_VLM_CACHE}"
DEVICE="${VLM_DEVICE:-cuda}"
BATCH_SIZE="${VLM_BATCH_SIZE:-32}"
ALLOW_NETWORK=0
CAMERA_IDS=()
FRAME_INDEXES=()

usage() {
  cat >&2 <<'EOF'
Usage: bash scripts/prepare_vlm_filter_view.sh [options]

Required:
  --episode PATH              Admitted filter_training.jsonl with residual_target_rad
  --camera ID=INDEX_JSONL     Repeat once per camera, in the desired concat order
  --output-dir PATH           New derived output directory

Options:
  --model-id ID               Default: google/siglip2-base-patch16-224
  --revision REV              Default: main; resolved commit is recorded
  --cache-dir PATH            Local Hugging Face cache
  --device DEVICE             Default: cuda
  --batch-size N              Default: 32
  --allow-network             Permit transformers network access (offline by default)
EOF
}

while (($#)); do
  case "$1" in
    --episode) EPISODE="${2:-}"; shift 2 ;;
    --camera)
      spec="${2:-}"
      [[ "$spec" == *=* ]] || { echo "[FATAL] --camera must be ID=INDEX_JSONL" >&2; exit 2; }
      CAMERA_IDS+=("${spec%%=*}")
      FRAME_INDEXES+=("${spec#*=}")
      shift 2
      ;;
    --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
    --model-id) MODEL_ID="${2:-}"; shift 2 ;;
    --revision) REVISION="${2:-}"; shift 2 ;;
    --cache-dir) CACHE_DIR="${2:-}"; shift 2 ;;
    --device) DEVICE="${2:-}"; shift 2 ;;
    --batch-size) BATCH_SIZE="${2:-}"; shift 2 ;;
    --allow-network) ALLOW_NETWORK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; echo "[FATAL] unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$EPISODE" ]] || { echo "[FATAL] episode JSONL not found: $EPISODE" >&2; exit 2; }
[[ -n "$OUTPUT_DIR" ]] || { usage; echo "[FATAL] --output-dir is required" >&2; exit 2; }
((${#CAMERA_IDS[@]} > 0)) || { usage; echo "[FATAL] at least one --camera is required" >&2; exit 2; }
[[ ! -e "$OUTPUT_DIR" ]] || { echo "[FATAL] refusing to overwrite: $OUTPUT_DIR" >&2; exit 2; }
for index in "${FRAME_INDEXES[@]}"; do
  [[ -f "$index" ]] || { echo "[FATAL] frame index not found: $index" >&2; exit 2; }
done
if ((${#CAMERA_IDS[@]} != $(printf '%s\n' "${CAMERA_IDS[@]}" | sort -u | wc -l))); then
  echo "[FATAL] camera IDs must be unique" >&2
  exit 2
fi

ENV_PREFIX="$(resolve_training_env_prefix)" || {
  echo "[FATAL] training environment not found; run scripts/install_vlm.sh" >&2
  exit 2
}
PYTHON="$ENV_PREFIX/bin/python"
[[ -x "$PYTHON" ]] || { echo "[FATAL] Python not found: $PYTHON" >&2; exit 2; }

mkdir -p "$OUTPUT_DIR"
EMBEDDINGS="$OUTPUT_DIR/vlm_embeddings.jsonl"
FILTER_VIEW="$OUTPUT_DIR/filter_training_vlm.jsonl"
encode=(
  "$PYTHON" "$ROOT_DIR/tools/encode_images_with_vlm.py"
  --output "$EMBEDDINGS" --model-id "$MODEL_ID" --revision "$REVISION"
  --cache-dir "$CACHE_DIR" --device "$DEVICE" --batch-size "$BATCH_SIZE"
)
for index in "${FRAME_INDEXES[@]}"; do encode+=(--frames "$index"); done
for camera_id in "${CAMERA_IDS[@]}"; do encode+=(--camera-id "$camera_id"); done
if ((ALLOW_NETWORK == 0)); then encode+=(--local-files-only); fi

echo "[1/2] frozen VLM embeddings"
"${encode[@]}"

attach=(
  "$PYTHON" "$ROOT_DIR/tools/attach_vlm_embeddings.py"
  --episode "$EPISODE" --embeddings "$EMBEDDINGS" --output "$FILTER_VIEW"
  --model-id "$MODEL_ID" --model-revision "$REVISION"
)
for camera_id in "${CAMERA_IDS[@]}"; do attach+=(--camera-id "$camera_id"); done

echo "[2/2] timestamp alignment and filter-view contract"
"${attach[@]}"
echo "[DONE] $FILTER_VIEW"
