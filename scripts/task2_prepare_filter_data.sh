#!/usr/bin/env bash
# Prepare every Task2 (button press) episode into a filter-training VLM view.
# Run inside the teleop conda environment:
#   conda activate teleop
#   bash scripts/task2_prepare_filter_data.sh
# Log is written automatically next to the model outputs under
# <run_root>/logs/ while still being printed to the terminal.
# Overrides: TASK2_DATA_DIR, TASK2_FLYWHEEL_CONFIG, TASK2_DERIVED_NAME,
#            TASK2_RUN_ROOT, TASK2_LOG_DIR
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${TASK2_DATA_DIR:-/media/fanshihao/UBUNTU 20_0/task_button_press/act_train_ready}"
CONFIG="${TASK2_FLYWHEEL_CONFIG:-$ROOT_DIR/config/flywheel/task2_button_press_local.yaml}"
DERIVED_NAME="${TASK2_DERIVED_NAME:-task2_button_press_v1}"
RUN_ROOT="${TASK2_RUN_ROOT:-/media/fanshihao/UBUNTU 20_0/task_button_press/filter_runs}"
LOG_DIR="${TASK2_LOG_DIR:-$RUN_ROOT/logs}"

export LEROBOT_ENV_NAME="${LEROBOT_ENV_NAME:-${CONDA_DEFAULT_ENV:-teleop}}"
# Drop ROS/system dist-packages from PYTHONPATH so the teleop interpreter uses
# its own numpy/sympy/transformers stack.
export PYTHONPATH=""

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/prepare_$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee "$LOG_FILE") 2>&1
trap 'wait' EXIT
echo "[LOG] $LOG_FILE"

if ! python -c 'import torch, transformers, tensorboard' >/dev/null 2>&1; then
  echo "[FATAL] teleop environment is not active or dependencies missing" >&2
  echo "Run: conda activate teleop" >&2
  exit 2
fi

[[ -d "$DATA_DIR" ]] || { echo "[FATAL] data dir not found: $DATA_DIR" >&2; exit 2; }
[[ -f "$CONFIG" ]] || { echo "[FATAL] flywheel config not found: $CONFIG" >&2; exit 2; }

mapfile -t RUNS < <(
  find "$DATA_DIR" -mindepth 1 -maxdepth 1 -type d -name '2026*' -print | sort
)
total="${#RUNS[@]}"
if (( total == 0 )); then
  echo "[FATAL] no episode directories found under: $DATA_DIR" >&2
  exit 2
fi

prepared=0
failed=0
index=0
for run in "${RUNS[@]}"; do
  index=$((index + 1))
  [[ -d "$run" ]] || continue
  name="$(basename "$run")"
  echo "[PREPARE] ($index/$total) $((index * 100 / total))% | $name"
  if python "$ROOT_DIR/tools/run_flywheel.py" "$run" --config "$CONFIG" --prepare-only; then
    prepared=$((prepared + 1))
  else
    echo "[FAIL] $name"
    failed=$((failed + 1))
  fi
done

view_count="$(find "$DATA_DIR" -path "*/derived/${DERIVED_NAME}/filter/vlm/filter_training_vlm.jsonl" | wc -l | tr -d ' ')"
echo "-----------------------------------------"
echo "[DONE] attempted=$prepared failed=$failed prepared_views=$view_count"
echo "View list saved per episode under: <episode>/derived/${DERIVED_NAME}/filter/vlm/filter_training_vlm.jsonl"
echo "[LOG] $LOG_FILE"

(( view_count > 0 ))
