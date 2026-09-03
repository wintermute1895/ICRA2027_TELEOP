#!/usr/bin/env bash
# Convert one completed real ROS2 run into an official local LeRobot v3 dataset.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/training_env.sh"
RUN_DIR=""
OUTPUT_DIR=""
AUDIT=""
CAMERA_TOPIC="/camera/camera/color/image_raw"
CAMERA_ID="main_rgb"
CAMERA_SPECS=()
TASK_ID="precision_alignment"
TASK_FAMILY="precision_alignment"
SUCCESS_SPEC="precision_alignment_v1"
TASK_TEXT="precision alignment"
REPO_ID="local/icra2027-teleop"
ACTION_CONTRACT="arm7"

usage() {
  cat >&2 <<'EOF'
Usage: scripts/convert_episode_to_lerobot.sh --run-dir PATH [options]

Options:
  --output-dir PATH       derived output (default: RUN/derived/lerobot-<UTC>)
  --audit PATH            terminal audit (default: RUN/artifacts/terminal_audit.json)
  --camera-topic TOPIC    RGB topic to project
  --camera-id ID          LeRobot camera feature suffix (default: main_rgb)
  --camera ID=TOPIC       RGB camera mapping; repeat for multiple cameras
  --task-id ID            structured task id
  --task-family ID        structured task family
  --success-spec ID       success specification version
  --task-text TEXT        natural-language LeRobot task
  --repo-id ID            local LeRobot repository id
  --action-contract NAME  arm7 (default) or arm7_hand6 exploratory contract

The source rosbag and terminal audit are read-only. The command refuses to
overwrite output and refuses policy projection when the real audit does not
admit the episode for policy_training.
EOF
}

while (($#)); do
  case "$1" in
    --run-dir) RUN_DIR="${2:-}"; shift 2 ;;
    --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
    --audit) AUDIT="${2:-}"; shift 2 ;;
    --camera-topic) CAMERA_TOPIC="${2:-}"; shift 2 ;;
    --camera-id) CAMERA_ID="${2:-}"; shift 2 ;;
    --camera) CAMERA_SPECS+=("${2:-}"); shift 2 ;;
    --task-id) TASK_ID="${2:-}"; shift 2 ;;
    --task-family) TASK_FAMILY="${2:-}"; shift 2 ;;
    --success-spec) SUCCESS_SPEC="${2:-}"; shift 2 ;;
    --task-text) TASK_TEXT="${2:-}"; shift 2 ;;
    --repo-id) REPO_ID="${2:-}"; shift 2 ;;
    --action-contract) ACTION_CONTRACT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$RUN_DIR" ]] || { usage; exit 2; }
RUN_DIR="$(realpath "$RUN_DIR")"
[[ -d "$RUN_DIR/artifacts/rosbag2" ]] || { echo "[FATAL] rosbag not found: $RUN_DIR/artifacts/rosbag2" >&2; exit 2; }
AUDIT="${AUDIT:-$RUN_DIR/artifacts/terminal_audit.json}"
[[ -f "$AUDIT" ]] || { echo "[FATAL] terminal audit not found: $AUDIT" >&2; exit 2; }
OUTPUT_DIR="${OUTPUT_DIR:-$RUN_DIR/derived/lerobot-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ ! -e "$OUTPUT_DIR" ]] || { echo "[FATAL] refusing to overwrite: $OUTPUT_DIR" >&2; exit 2; }

ENV_PREFIX="$(resolve_training_env_prefix)" || { echo "[FATAL] training environment not found; run scripts/install_lerobot.sh" >&2; exit 2; }
TRAIN_PYTHON="$ENV_PREFIX/bin/python"
[[ -x "$TRAIN_PYTHON" ]] || { echo "[FATAL] training Python not found; run scripts/install_lerobot.sh" >&2; exit 2; }
ROS_PYTHON="${ROS_PYTHON:-/usr/bin/python3}"
ROS_SETUP=""
for distro in "${ROS_DISTRO:-}" jazzy humble; do
  [[ -n "$distro" && -f "/opt/ros/$distro/setup.bash" ]] || continue
  ROS_SETUP="/opt/ros/$distro/setup.bash"
  break
done
[[ -n "$ROS_SETUP" ]] || { echo "[FATAL] ROS2 Jazzy or Humble was not found" >&2; exit 2; }
[[ -f "$ROOT_DIR/ros2_ws/install/setup.bash" ]] || {
  echo "[FATAL] ROS workspace is not built; run scripts/build_ros2_workspace.sh" >&2
  exit 2
}
set +u
source "$ROS_SETUP"
source "$ROOT_DIR/ros2_ws/install/setup.bash"
set -u
PYTHONPATH="$ROOT_DIR/tools${PYTHONPATH:+:$PYTHONPATH}" "$ROS_PYTHON" - <<'PY'
import lbot_arm_interfaces.msg
import rosbag2_py
PY

EXPORT_DIR="$OUTPUT_DIR/export"
FRAME_DIR="$OUTPUT_DIR/frames"
CANONICAL_DIR="$OUTPUT_DIR/canonical-right"
ACT_DIR="$OUTPUT_DIR/act"
LEROBOT_DIR="$OUTPUT_DIR/lerobot"
FILTER_DIR="$OUTPUT_DIR/filter"
mkdir -p "$EXPORT_DIR" "$FRAME_DIR"

CAMERA_IDS=()
CAMERA_TOPICS=()
if ((${#CAMERA_SPECS[@]})); then
  for spec in "${CAMERA_SPECS[@]}"; do
    [[ "$spec" == *=* ]] || { echo "[FATAL] --camera expects ID=TOPIC: $spec" >&2; exit 2; }
    camera_id="${spec%%=*}"
    camera_topic="${spec#*=}"
    [[ -n "$camera_id" && "$camera_topic" == /*/color/image_raw ]] || {
      echo "[FATAL] invalid --camera mapping: $spec" >&2
      exit 2
    }
    CAMERA_IDS+=("$camera_id")
    CAMERA_TOPICS+=("$camera_topic")
  done
else
  CAMERA_IDS+=("$CAMERA_ID")
  CAMERA_TOPICS+=("$CAMERA_TOPIC")
fi

declare -A SEEN_CAMERA_IDS=()
for camera_id in "${CAMERA_IDS[@]}"; do
  [[ -z "${SEEN_CAMERA_IDS[$camera_id]+x}" ]] || {
    echo "[FATAL] duplicate camera id: $camera_id" >&2
    exit 2
  }
  SEEN_CAMERA_IDS[$camera_id]=1
done

EXPORT_CAMERA_ARGS=(--camera-namespace "${CAMERA_TOPICS[0]%/color/image_raw}" --camera-id "${CAMERA_IDS[0]}")
for ((index = 1; index < ${#CAMERA_IDS[@]}; index++)); do
  EXPORT_CAMERA_ARGS+=(--extra-camera-namespace "${CAMERA_TOPICS[index]%/color/image_raw}" --camera-id "${CAMERA_IDS[index]}")
done

echo "[1/5] rosbag2 -> aligned right-arm JSONL"
PYTHONPATH="$ROOT_DIR/tools${PYTHONPATH:+:$PYTHONPATH}" "$ROS_PYTHON" "$ROOT_DIR/tools/export_rosbag_episode.py" \
  --bag "$RUN_DIR/artifacts/rosbag2" --output "$EXPORT_DIR/right_episode.jsonl" \
  --arm right --source-domain real "${EXPORT_CAMERA_ARGS[@]}"

echo "[2/5] decode RGB frames (${#CAMERA_IDS[@]} camera(s))"
for ((index = 0; index < ${#CAMERA_IDS[@]}; index++)); do
  PYTHONPATH="$ROOT_DIR/tools${PYTHONPATH:+:$PYTHONPATH}" "$ROS_PYTHON" "$ROOT_DIR/tools/extract_rosbag_images.py" \
    --bag "$RUN_DIR/artifacts/rosbag2" --topic "${CAMERA_TOPICS[index]}" \
    --output-dir "$FRAME_DIR" --camera-id "${CAMERA_IDS[index]}"
done

echo "[3/5] aligned JSONL -> canonical v0.1"
PYTHONPATH="$ROOT_DIR/tools${PYTHONPATH:+:$PYTHONPATH}" "$ROS_PYTHON" "$ROOT_DIR/tools/exported_jsonl_to_canonical_episode.py" \
  --export-jsonl "$EXPORT_DIR/right_episode.jsonl" --output-dir "$CANONICAL_DIR" \
  --source real --task-id "$TASK_ID" --task-family "$TASK_FAMILY" \
  --success-spec-version "$SUCCESS_SPEC" --configuration-id unassigned \
  --collection-mode teleop_rule --terminal-audit "$AUDIT"

echo "[4/5] canonical -> training projections"
if "$TRAIN_PYTHON" - "$CANONICAL_DIR/episode.manifest.json" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
raise SystemExit(0 if "filter_training" in manifest.get("intended_uses", []) else 1)
PY
then
  PYTHONPATH="$ROOT_DIR/tools" "$ROS_PYTHON" "$ROOT_DIR/tools/canonical_episode_to_filter_jsonl.py" \
    --manifest "$CANONICAL_DIR/episode.manifest.json" \
    --output "$FILTER_DIR/filter_training.jsonl"
  echo "[INFO] admitted filter-training projection: $FILTER_DIR/filter_training.jsonl"
else
  echo "[INFO] episode is not admitted for filter training; LeRobot policy projection continues"
fi
ACT_CAMERA_ARGS=()
for camera_id in "${CAMERA_IDS[@]}"; do
  ACT_CAMERA_ARGS+=(--camera-id "$camera_id" --camera-index "$FRAME_DIR/${camera_id}_frames.jsonl")
done
PYTHONPATH="$ROOT_DIR/tools" "$TRAIN_PYTHON" "$ROOT_DIR/tools/canonical_episode_to_act_dataset.py" \
  --manifest "$CANONICAL_DIR/episode.manifest.json" --output-dir "$ACT_DIR" \
  "${ACT_CAMERA_ARGS[@]}" --copy-images

echo "[5/5] ACT projection -> official LeRobot v3"
HF_HOME="$OUTPUT_DIR/cache/huggingface" HF_DATASETS_CACHE="$OUTPUT_DIR/cache/huggingface/datasets" \
PYTHONPATH="$ROOT_DIR/tools" "$TRAIN_PYTHON" "$ROOT_DIR/tools/act_jsonl_to_lerobot.py" \
  --input-jsonl "$ACT_DIR/episode_000000.jsonl" --output-dir "$LEROBOT_DIR" \
  --repo-id "$REPO_ID" --task "$TASK_TEXT" --action-contract "$ACTION_CONTRACT" \
  --contract-config "$ROOT_DIR/config/act/action_contracts.yaml"

echo "[DONE] official LeRobot dataset: $LEROBOT_DIR"
