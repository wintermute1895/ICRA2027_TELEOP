#!/usr/bin/env bash
# Build a correction-aware filter view, optionally followed by frozen VLM attachment.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/training_env.sh"

# Stable pipeline settings belong in a versioned YAML file. Keep this legacy
# flag-based path for compatibility with existing automation.
ARGS=("$@")
for ((arg_index = 0; arg_index < ${#ARGS[@]}; arg_index++)); do
  arg="${ARGS[arg_index]}"
  if [[ "$arg" == --config=* || "$arg" == --config ]]; then
    ENV_PREFIX="$(resolve_training_env_prefix)" || {
      echo "[FATAL] training environment not found" >&2
      exit 2
    }
    if [[ "$arg" == --config=* ]]; then
      CONFIG_ARG="${arg#*=}"
    else
      ((arg_index += 1))
      CONFIG_ARG="${ARGS[arg_index]:-}"
    fi
    [[ -n "$CONFIG_ARG" ]] || { echo "[FATAL] --config requires a path" >&2; exit 2; }
    exec "${PIPELINE_PYTHON:-$ENV_PREFIX/bin/python}" "$ROOT_DIR/tools/prepare_filter_training_view.py" \
      --config "$CONFIG_ARG"
  fi
done

EPISODE=""
EVENTS=""
EXPERT_ACTION_FIELD=""
OUTPUT_DIR=""
CAMERA_SPECS=()
MODEL_ID="google/siglip2-base-patch16-224"
REVISION="main"
CACHE_DIR=""
DEVICE="cuda"
BATCH_SIZE="32"
MAX_AGE_MS="100.0"

usage() {
  cat >&2 <<'EOF'
Usage: scripts/prepare_filter_training_view.sh --episode PATH \
  --expert-action-field FIELD --output-dir PATH [options]

Preferred:
  --config PATH                  versioned YAML containing all pipeline settings

Required:
  --episode PATH                  canonical/filter-training JSONL source
  --expert-action-field FIELD     recorded action copied as expert target
  --output-dir PATH               new derived output directory

Options:
  --events PATH                   human audit events JSONL
  --camera ID=INDEX_JSONL          repeat to append frozen VLM embeddings
  --model-id ID                   default: google/siglip2-base-patch16-224
  --revision REV                  default: main
  --cache-dir PATH                local Hugging Face cache
  --device DEVICE                 default: cuda
  --batch-size N                  default: 32
  --max-age-ms N                 maximum timestamp alignment age (default: 100)
EOF
}

while (($#)); do
  case "$1" in
    --episode) EPISODE="${2:-}"; shift 2 ;;
    --events) EVENTS="${2:-}"; shift 2 ;;
    --expert-action-field) EXPERT_ACTION_FIELD="${2:-}"; shift 2 ;;
    --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
    --camera) CAMERA_SPECS+=("${2:-}"); shift 2 ;;
    --model-id) MODEL_ID="${2:-}"; shift 2 ;;
    --revision) REVISION="${2:-}"; shift 2 ;;
    --cache-dir) CACHE_DIR="${2:-}"; shift 2 ;;
    --device) DEVICE="${2:-}"; shift 2 ;;
    --batch-size) BATCH_SIZE="${2:-}"; shift 2 ;;
    --max-age-ms) MAX_AGE_MS="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; echo "[FATAL] unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$EPISODE" ]] || { usage; echo "[FATAL] episode not found: $EPISODE" >&2; exit 2; }
[[ -n "$EXPERT_ACTION_FIELD" ]] || { usage; echo "[FATAL] --expert-action-field is required" >&2; exit 2; }
[[ -n "$OUTPUT_DIR" ]] || { usage; echo "[FATAL] --output-dir is required" >&2; exit 2; }
[[ ! -e "$OUTPUT_DIR" ]] || { echo "[FATAL] refusing to overwrite: $OUTPUT_DIR" >&2; exit 2; }
if [[ -n "$EVENTS" ]]; then
  [[ -f "$EVENTS" ]] || { echo "[FATAL] events file not found: $EVENTS" >&2; exit 2; }
fi

ENV_PREFIX="${TRAINING_ENV_PREFIX:-$(resolve_training_env_prefix)}"
PYTHON="${ENV_PREFIX}/bin/python"
[[ -x "$PYTHON" ]] || { echo "[FATAL] training Python not found: $PYTHON" >&2; exit 2; }
mkdir -p "$OUTPUT_DIR"
CORRECTION_VIEW="$OUTPUT_DIR/correction_view.jsonl"
command=("$PYTHON" "$ROOT_DIR/tools/build_correction_segment_view.py" --episode "$EPISODE" --expert-action-field "$EXPERT_ACTION_FIELD" --output "$CORRECTION_VIEW")
[[ -z "$EVENTS" ]] || command+=(--events "$EVENTS")
echo "[1/2] correction segment view"
"${command[@]}"

if ((${#CAMERA_SPECS[@]} == 0)); then
  echo "[DONE] $CORRECTION_VIEW"
  exit 0
fi

VLMCMD=(bash "$ROOT_DIR/scripts/prepare_vlm_filter_view.sh" --episode "$CORRECTION_VIEW" --output-dir "$OUTPUT_DIR/vlm" --model-id "$MODEL_ID" --revision "$REVISION" --device "$DEVICE" --batch-size "$BATCH_SIZE" --max-age-ms "$MAX_AGE_MS")
[[ -z "$CACHE_DIR" ]] || VLMCMD+=(--cache-dir "$CACHE_DIR")
for spec in "${CAMERA_SPECS[@]}"; do VLMCMD+=(--camera "$spec"); done
echo "[2/2] frozen VLM attachment"
"${VLMCMD[@]}"
echo "[DONE] $OUTPUT_DIR/vlm/filter_training_vlm.jsonl"
