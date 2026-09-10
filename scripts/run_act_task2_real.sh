#!/usr/bin/env bash
# ACT task2-50hz 真机 rollout(单行命令封装,避免粘贴换行截断)
# 用法: bash scripts/run_act_task2_real.sh [record-dir后缀]
# 数据盘由 resolve_data_disk.sh 自动探测(可用 TELEOP_DATA_ROOT 覆盖)。
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
TAG="${1:-v2}"
DATA_ROOT="${TELEOP_DATA_ROOT:-$(bash scripts/resolve_data_disk.sh)}"
exec bash scripts/start_model_rollout.sh \
  --config config/runtime/rollout_active_test.yaml \
  --source act \
  --act-config config/runtime/act-task2-50hz.yaml \
  --real \
  --physical-estop-ready \
  --confirm=I_UNDERSTAND_REAL_ROLLOUT \
  --model-confirm=I_UNDERSTAND_MODEL_DEPLOYMENT \
  --record-dir "$DATA_ROOT/act_rollouts/task2/50hz_real_${TAG}"
