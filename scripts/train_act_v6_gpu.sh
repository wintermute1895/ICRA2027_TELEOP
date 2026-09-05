#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# All settings can be overridden through environment variables.
PYTHON_BIN="${DEX_TELEOP_PYTHON:-/home/dex/桌面/ICRA2027_TELEOP/.conda/envs/dex_teleop/bin/python}"
DATASET_ROOT="${LEROBOT_DATASET_ROOT:-/media/dex/Cyan_data/ICRA2027_TELEOP_DATA/lerobot_precision_alignment_50hz_v6_clean}"
DATASET_REPO_ID="${LEROBOT_DATASET_REPO_ID:-linker_a7_precision_alignment}"
SPLIT_NAME="${LEROBOT_SPLIT:-train}"
SPLIT_FILE="${LEROBOT_SPLIT_FILE:-${DATASET_ROOT}/meta/splits.json}"
OUTPUT_DIR="${ACT_OUTPUT_DIR:-/media/dex/Cyan_data/ICRA2027_TELEOP_DATA/act_checkpoints/act_full_gpu_run}"
CACHE_DIR="${ACT_CACHE_DIR:-${PROJECT_ROOT}/.cache}"
export TMPDIR="${ACT_TMPDIR:-/tmp}"

ACT_BATCH_SIZE="${ACT_BATCH_SIZE:-16}"
ACT_LR="${ACT_LR:-1e-5}"
ACT_WEIGHT_DECAY="${ACT_WEIGHT_DECAY:-1e-4}"
ACT_LR_BACKBONE="${ACT_LR_BACKBONE:-${ACT_LR}}"
ACT_KL_WEIGHT="${ACT_KL_WEIGHT:-10.0}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "DEX_TELEOP_PYTHON is not executable: ${PYTHON_BIN}" >&2
  exit 1
fi
if [[ ! -f "${DATASET_ROOT}/meta/info.json" ]]; then
  echo "LeRobot dataset metadata is missing: ${DATASET_ROOT}/meta/info.json" >&2
  exit 1
fi

if [[ -f "${SPLIT_FILE}" ]]; then
  EPISODES="$(${PYTHON_BIN} - "${SPLIT_FILE}" "${SPLIT_NAME}" <<'PY'
import json
import sys
from pathlib import Path

split_file, split_name = Path(sys.argv[1]), sys.argv[2]
data = json.loads(split_file.read_text(encoding="utf-8"))
try:
    indices = data[split_name]["episode_indices"]
except (KeyError, TypeError):
    raise SystemExit(f"split {split_name!r} is not present in {split_file}")
if not indices:
    raise SystemExit(f"split {split_name!r} is empty")
print("[" + ",".join(str(int(index)) for index in indices) + "]")
PY
)"
else
  if [[ "${SPLIT_NAME}" != "train" && "${SPLIT_NAME}" != "all" ]]; then
    echo "Episode split file is missing: ${SPLIT_FILE}" >&2
    exit 1
  fi
  EPISODES="$(${PYTHON_BIN} - "${DATASET_ROOT}/meta/info.json" <<'PY'
import json
import sys
from pathlib import Path

info = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
total = int(info["total_episodes"])
if total <= 0:
    raise SystemExit("dataset has no episodes")
print("[" + ",".join(str(index) for index in range(total)) + "]")
PY
)"
  echo "split file not found; using all episodes" >&2
fi

# LeRobot steps are optimizer updates. By default, compute 100 complete passes
# over the selected episodes and save one checkpoint every 20 epochs.
if [[ -n "${ACT_STEPS:-}" ]]; then
  TRAIN_STEPS="${ACT_STEPS}"
  TRAIN_EPOCHS="manual"
  SAVE_FREQ="${ACT_SAVE_FREQ:-250}"
else
  TRAIN_EPOCHS="${ACT_EPOCHS:-100}"
  if ! [[ "${TRAIN_EPOCHS}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ACT_EPOCHS must be a positive integer: ${TRAIN_EPOCHS}" >&2
    exit 1
  fi
  TRAIN_PLAN="$(${PYTHON_BIN} - "${DATASET_ROOT}" "${EPISODES}" "${ACT_BATCH_SIZE}" "${TRAIN_EPOCHS}" <<'PY'
import json
import math
import sys
from pathlib import Path

root = Path(sys.argv[1])
episodes = [int(value) for value in json.loads(sys.argv[2])]
batch_size = int(sys.argv[3])
epochs = int(sys.argv[4])
lengths = {}
with (root / "meta" / "episodes.jsonl").open(encoding="utf-8") as stream:
    for line in stream:
        row = json.loads(line)
        lengths[int(row["episode_index"])] = int(row["length"])
missing = [episode for episode in episodes if episode not in lengths]
if missing:
    raise SystemExit(f"episode metadata missing for: {missing}")
frames = sum(lengths[episode] for episode in episodes)
if frames <= 0 or batch_size <= 0:
    raise SystemExit("dataset frames and batch size must be positive")
steps_per_epoch = math.ceil(frames / batch_size)
print(steps_per_epoch, steps_per_epoch * epochs)
PY
)"
  read -r STEPS_PER_EPOCH TRAIN_STEPS <<< "${TRAIN_PLAN}"
  SAVE_EPOCHS="${ACT_SAVE_EPOCHS:-20}"
  if ! [[ "${SAVE_EPOCHS}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ACT_SAVE_EPOCHS must be a positive integer: ${SAVE_EPOCHS}" >&2
    exit 1
  fi
  SAVE_FREQ="${ACT_SAVE_FREQ:-$((STEPS_PER_EPOCH * SAVE_EPOCHS))}"
fi

mkdir -p "${CACHE_DIR}/huggingface" "${CACHE_DIR}/torch" "$(dirname "${OUTPUT_DIR}")"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export HF_HOME="${HF_HOME:-${CACHE_DIR}/huggingface}"
export TORCH_HOME="${TORCH_HOME:-${CACHE_DIR}/torch}"

FRAMES_PER_EPOCH="$(${PYTHON_BIN} - "${DATASET_ROOT}" "${EPISODES}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
episodes = set(int(value) for value in json.loads(sys.argv[2]))
frames = 0
with (root / "meta" / "episodes.jsonl").open(encoding="utf-8") as stream:
    for line in stream:
        row = json.loads(line)
        if int(row["episode_index"]) in episodes:
            frames += int(row["length"])
print(frames)
PY
)"

echo "ACT policy"
echo "dataset=${DATASET_ROOT}"
echo "split=${SPLIT_NAME} episodes=${EPISODES}"
echo "frames_per_epoch=${FRAMES_PER_EPOCH} batch_size=${ACT_BATCH_SIZE} epochs=${TRAIN_EPOCHS} steps=${TRAIN_STEPS} save_freq=${SAVE_FREQ}"
if [[ -n "${STEPS_PER_EPOCH:-}" ]]; then
  echo "checkpoint_interval_epochs=${SAVE_EPOCHS} (override with ACT_SAVE_FREQ)"
fi
echo "output=${OUTPUT_DIR}"
echo "optimizer_lr=${ACT_LR} optimizer_lr_backbone=${ACT_LR_BACKBONE} weight_decay=${ACT_WEIGHT_DECAY} kl_weight=${ACT_KL_WEIGHT}"

if [[ "${ACT_DRY_RUN:-0}" == "1" ]]; then
  echo "ACT_DRY_RUN=1; training was not started"
  exit 0
fi

PYTHONNOUSERSITE=1 "${PYTHON_BIN}" "${SCRIPT_DIR}/train_act_v6.py" \
  --policy.type=act \
  --dataset.repo_id="${DATASET_REPO_ID}" \
  --dataset.root="${DATASET_ROOT}" \
  --dataset.episodes="${EPISODES}" \
  --policy.device=cuda \
  --policy.use_amp=true \
  --policy.push_to_hub=false \
  --policy.pretrained_backbone_weights=null \
  --policy.optimizer_lr="${ACT_LR}" \
  --policy.optimizer_weight_decay="${ACT_WEIGHT_DECAY}" \
  --policy.optimizer_lr_backbone="${ACT_LR_BACKBONE}" \
  --policy.kl_weight="${ACT_KL_WEIGHT}" \
  --batch_size="${ACT_BATCH_SIZE}" \
  --steps="${TRAIN_STEPS}" \
  --eval_freq=0 \
  --log_freq="${ACT_LOG_FREQ:-10}" \
  --save_freq="${SAVE_FREQ}" \
  --save_checkpoint=true \
  --num_workers="${ACT_NUM_WORKERS:-4}" \
  --output_dir="${OUTPUT_DIR}" \
  --wandb.enable=false
