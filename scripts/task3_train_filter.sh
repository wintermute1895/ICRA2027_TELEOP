#!/usr/bin/env bash
# Train the task-aware residual filter (v0.2 + SigLIP2) over all prepared
# Task3 views. The last 10 sorted views are held out as validation.
# Run inside the teleop conda environment:
#   conda activate teleop
#   bash scripts/task3_train_filter.sh            # round1, 50 epochs, batch 64
#   TASK3_ROUND=round2 TASK3_EPOCHS=80 bash scripts/task3_train_filter.sh
# Log is written automatically next to the model outputs under
# <run_root>/logs/ while still being printed to the terminal.
# Overrides: TASK3_DATA_DIR, TASK3_DERIVED_NAME, TASK3_RUN_ROOT,
#            TASK3_MODEL_CONFIG, TASK3_ROUND, TASK3_EPOCHS, TASK3_BATCH,
#            TASK3_VALIDATION_COUNT, TASK3_DEVICE, TASK3_LOG_DIR
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${TASK3_DATA_DIR:-/media/fanshihao/Cyan_data/ICRA2027_DATA/Task_Data/task3_Data}"
DERIVED_NAME="${TASK3_DERIVED_NAME:-task3_screwdriver_v1}"
RUN_ROOT="${TASK3_RUN_ROOT:-/media/fanshihao/Cyan_data/ICRA2027_DATA/Task_Data/task3_Data/filter_runs}"
LOG_DIR="${TASK3_LOG_DIR:-$RUN_ROOT/logs}"
MODEL_CONFIG="${TASK3_MODEL_CONFIG:-$ROOT_DIR/config/filters/trajectory_cvae_transformer_v0_2_vlm.yaml}"
ROUND="${TASK3_ROUND:-round1}"
EPOCHS="${TASK3_EPOCHS:-50}"
BATCH="${TASK3_BATCH:-64}"
VALIDATION_COUNT="${TASK3_VALIDATION_COUNT:-10}"
DEVICE="${TASK3_DEVICE:-cuda}"

export LEROBOT_ENV_NAME="${LEROBOT_ENV_NAME:-${CONDA_DEFAULT_ENV:-teleop}}"
# Drop ROS/system dist-packages from PYTHONPATH so the teleop interpreter uses
# its own numpy/sympy/transformers stack.
export PYTHONPATH=""

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/train_${ROUND}_$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee "$LOG_FILE") 2>&1
trap 'wait' EXIT
echo "[LOG] $LOG_FILE"

if ! python -c 'import torch, tensorboard' >/dev/null 2>&1; then
  echo "[FATAL] teleop environment is not active or dependencies missing" >&2
  echo "Run: conda activate teleop" >&2
  exit 2
fi

[[ -d "$DATA_DIR" ]] || { echo "[FATAL] data dir not found: $DATA_DIR" >&2; exit 2; }
[[ -f "$MODEL_CONFIG" ]] || { echo "[FATAL] model config not found: $MODEL_CONFIG" >&2; exit 2; }

mapfile -t VIEWS < <(
  find "$DATA_DIR" -path "*/derived/${DERIVED_NAME}/filter/vlm/filter_training_vlm.jsonl" -print | sort
)
total="${#VIEWS[@]}"
if (( total < VALIDATION_COUNT + 1 )); then
  echo "[FATAL] need at least $((VALIDATION_COUNT + 1)) prepared views, found $total" >&2
  echo "Run scripts/task3_prepare_filter_data.sh first." >&2
  exit 2
fi

ROUND_DIR="$RUN_ROOT/$ROUND"
if [[ -e "$ROUND_DIR/model" ]]; then
  echo "[FATAL] refusing to overwrite existing model: $ROUND_DIR/model" >&2
  echo "Set TASK3_ROUND=round2 (or another name) to retrain." >&2
  exit 2
fi
mkdir -p "$ROUND_DIR"

validation=("${VIEWS[@]: -$VALIDATION_COUNT}")
train=("${VIEWS[@]:0:$((total - VALIDATION_COUNT))}")

printf '%s\n' "${validation[@]}" > "$ROUND_DIR/validation_views.txt"

cmd=(
  python "$ROOT_DIR/tools/train_trajectory_filter.py"
  --config "$MODEL_CONFIG"
  --output-dir "$ROUND_DIR/model"
  --device "$DEVICE" --require-cuda
  --epochs "$EPOCHS" --batch-size "$BATCH"
  --tensorboard-logdir "$ROUND_DIR/tensorboard"
)
for view in "${train[@]}"; do
  cmd+=(--episode "$view")
done
for view in "${validation[@]}"; do
  cmd+=(--validation-episode "$view")
done

echo "[TRAIN] round=$ROUND train=$((total - VALIDATION_COUNT)) validation=$VALIDATION_COUNT total=$total"
echo "[TRAIN] output=$ROUND_DIR/model"
"${cmd[@]}"

echo "[DONE] checkpoint: $ROUND_DIR/model/trajectory_filter.pt"
echo "[DONE] validation views: $ROUND_DIR/validation_views.txt"
echo "[LOG] $LOG_FILE"
