#!/usr/bin/env bash
# Evaluate a Task1 filter checkpoint on the held-out views recorded by the
# train script (last 3 sorted views).
# Run inside the teleop conda environment:
#   conda activate teleop
#   bash scripts/task1_evaluate_filter.sh         # evaluates round1
#   TASK1_ROUND=round2 bash scripts/task1_evaluate_filter.sh
# Log is written automatically next to the model outputs under
# <run_root>/logs/ while still being printed to the terminal.
# Overrides: TASK1_RUN_ROOT, TASK1_ROUND, TASK1_DEVICE, TASK1_LOG_DIR
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ROOT="${TASK1_RUN_ROOT:-/media/fanshihao/Cyan_data/ICRA2027_DATA/Task_Data/Task1_Data/filter_runs}"
LOG_DIR="${TASK1_LOG_DIR:-$RUN_ROOT/logs}"
ROUND="${TASK1_ROUND:-round1}"
DEVICE="${TASK1_DEVICE:-cuda}"

# Drop ROS/system dist-packages from PYTHONPATH so the teleop interpreter uses
# its own numpy/sympy stack.
export PYTHONPATH=""

ROUND_DIR="$RUN_ROOT/$ROUND"
CHECKPOINT="$ROUND_DIR/model/trajectory_filter.pt"
VIEW_FILE="$ROUND_DIR/validation_views.txt"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/eval_${ROUND}_$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee "$LOG_FILE") 2>&1
trap 'wait' EXIT
echo "[LOG] $LOG_FILE"

[[ -f "$CHECKPOINT" ]] || { echo "[FATAL] checkpoint not found: $CHECKPOINT" >&2; exit 2; }
[[ -f "$VIEW_FILE" ]] || { echo "[FATAL] validation view list not found: $VIEW_FILE" >&2; exit 2; }

mapfile -t VALIDATION < "$VIEW_FILE"
if (( ${#VALIDATION[@]} == 0 )); then
  echo "[FATAL] validation view list is empty: $VIEW_FILE" >&2
  exit 2
fi

if [[ -e "$ROUND_DIR/evaluation" ]]; then
  echo "[FATAL] refusing to overwrite existing evaluation: $ROUND_DIR/evaluation" >&2
  echo "Set TASK1_ROUND to a new round or remove the directory." >&2
  exit 2
fi

cmd=(
  python "$ROOT_DIR/tools/evaluate_trajectory_filter.py"
  --checkpoint "$CHECKPOINT"
  --output-dir "$ROUND_DIR/evaluation"
  --device "$DEVICE"
)
for view in "${VALIDATION[@]}"; do
  cmd+=(--episode "$view")
done

echo "[EVAL] round=$ROUND episodes=${#VALIDATION[@]}"
"${cmd[@]}"

echo "[DONE] report: $ROUND_DIR/evaluation/evaluation_report.json"
echo "[LOG] $LOG_FILE"
