#!/usr/bin/env bash
# Offline smoke test for rosbag2 -> JSONL -> canonical -> ACT/LeRobot-ready.
# The source rosbag and its original terminal audit are never modified.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${1:-$ROOT_DIR/evidence/teleop/20260831T051917Z_precision_assembly_ab_v1-unassigned-episode-2_a06d42}"
source "$ROOT_DIR/scripts/lib/training_env.sh"
ENV_PREFIX="$(resolve_training_env_prefix)" || { echo "[FATAL] training environment not found; run scripts/install_lerobot.sh" >&2; exit 2; }
PYTHON="${ENV_PREFIX}/bin/python"
ROS_PYTHON="${ROS_PYTHON:-/usr/bin/python3}"
ROS_SETUP="${ROS_SETUP:-}"
for distro in "${ROS_DISTRO:-}" jazzy humble; do
  [[ -n "$distro" && -f "/opt/ros/$distro/setup.bash" ]] || continue
  ROS_SETUP="/opt/ros/$distro/setup.bash"
  break
done

[[ -x "$PYTHON" ]] || { echo "[FATAL] Python not found: $PYTHON" >&2; exit 2; }
[[ -x "$ROS_PYTHON" ]] || { echo "[FATAL] ROS Python not found: $ROS_PYTHON" >&2; exit 2; }
[[ -d "$RUN_DIR/artifacts/rosbag2" ]] || { echo "[FATAL] rosbag not found under: $RUN_DIR" >&2; exit 2; }
[[ -n "$ROS_SETUP" ]] || { echo "[FATAL] no ROS2 setup found under /opt/ros" >&2; exit 2; }

# ROS setup scripts legitimately reference unset variables on some distros.
set +u
source "$ROS_SETUP"
if [[ -f "$ROOT_DIR/ros2_ws/install/setup.bash" ]]; then
  source "$ROOT_DIR/ros2_ws/install/setup.bash"
else
  echo "[FATAL] ROS workspace is not built: $ROOT_DIR/ros2_ws/install/setup.bash" >&2
  echo "        Build it with: cd $ROOT_DIR/ros2_ws && colcon build --symlink-install" >&2
  exit 2
fi
set -u

PYTHONPATH="$ROOT_DIR/tools${PYTHONPATH:+:$PYTHONPATH}" "$ROS_PYTHON" - <<'PY'
import lbot_arm_interfaces.msg
import rosbag2_py
print("[PASS] ROS Python can import rosbag2_py and lbot_arm_interfaces")
PY

SMOKE_ID="${LEROBOT_SMOKE_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
DERIVED="$RUN_DIR/derived/lerobot-smoke-$SMOKE_ID"
EXPORT_DIR="$DERIVED/export"
FRAME_DIR="$DERIVED/frames"
CANONICAL_DIR="$DERIVED/canonical-right"
ACT_DIR="$DERIVED/act"
LEROBOT_DIR="$DERIVED/lerobot"
TEST_AUDIT="$DERIVED/conversion-smoke-audit.json"

[[ ! -e "$DERIVED" ]] || { echo "[FATAL] refusing to overwrite existing test output: $DERIVED" >&2; exit 2; }
mkdir -p "$EXPORT_DIR" "$FRAME_DIR"

RUN_ID="$(basename "$RUN_DIR")"
"$PYTHON" - "$TEST_AUDIT" "$RUN_ID" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(json.dumps({
    "schema": "robot_teleop.terminal-audit/v0.1",
    "episode_id": sys.argv[2],
    "success": True,
    "termination_reason": "conversion_smoke_test_only",
    "safety_violation": False,
    "unlogged_external_override": False,
    "audit_source": "conversion_smoke_fixture",
    "operator_id": "conversion_smoke",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "evidence_refs": ["../artifacts/rosbag2"],
}, indent=2) + "\n", encoding="utf-8")
PY

echo "[1/5] rosbag2 -> right-arm JSONL"
PYTHONPATH="$ROOT_DIR/tools${PYTHONPATH:+:$PYTHONPATH}" "$ROS_PYTHON" "$ROOT_DIR/tools/export_rosbag_episode.py" \
  --bag "$RUN_DIR/artifacts/rosbag2" \
  --output "$EXPORT_DIR/right_episode.jsonl" \
  --arm right \
  --source-domain real \
  --camera-namespace /camera/camera \
  --extra-camera-namespace /camera2/camera \
  --camera-id main_rgb \
  --camera-id auxiliary_rgb

echo "[2/5] decode both RGB streams"
for camera_spec in \
  "main_rgb=/camera/camera/color/image_raw" \
  "auxiliary_rgb=/camera2/camera/color/image_raw"; do
  camera_id="${camera_spec%%=*}"
  camera_topic="${camera_spec#*=}"
  PYTHONPATH="$ROOT_DIR/tools${PYTHONPATH:+:$PYTHONPATH}" "$ROS_PYTHON" "$ROOT_DIR/tools/extract_rosbag_images.py" \
    --bag "$RUN_DIR/artifacts/rosbag2" \
    --topic "$camera_topic" \
    --output-dir "$FRAME_DIR" \
    --camera-id "$camera_id"
done

echo "[3/5] JSONL -> canonical v0.1"
PYTHONPATH="$ROOT_DIR/tools${PYTHONPATH:+:$PYTHONPATH}" "$ROS_PYTHON" "$ROOT_DIR/tools/exported_jsonl_to_canonical_episode.py" \
  --export-jsonl "$EXPORT_DIR/right_episode.jsonl" \
  --output-dir "$CANONICAL_DIR" \
  --source real \
  --task-id precision_alignment \
  --task-family precision_alignment \
  --success-spec-version precision_alignment_v1 \
  --configuration-id conversion_smoke \
  --collection-mode teleop_rule \
  --terminal-audit "$TEST_AUDIT"

echo "[4/5] canonical -> ACT projection"
PYTHONPATH="$ROOT_DIR/tools" "$PYTHON" "$ROOT_DIR/tools/canonical_episode_to_act_dataset.py" \
  --manifest "$CANONICAL_DIR/episode.manifest.json" \
  --output-dir "$ACT_DIR" \
  --camera-id main_rgb \
  --camera-index "$FRAME_DIR/main_rgb_frames.jsonl" \
  --camera-id auxiliary_rgb \
  --camera-index "$FRAME_DIR/auxiliary_rgb_frames.jsonl" \
  --copy-images

"$PYTHON" - "$ACT_DIR/episode_000000.jsonl" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
required = {
    "observation.state", "action", "observation.images.main_rgb",
    "observation.images.auxiliary_rgb", "next.done",
}
missing = required.difference(rows[0]) if rows else required
if missing:
    raise SystemExit(f"missing LeRobot/ACT fields: {sorted(missing)}")
print(f"[PASS] {len(rows)} rows; keys and copied images verified")
PY

echo "[5/5] ACT projection -> official LeRobot v3 dataset"
HF_HOME="$DERIVED/cache/huggingface" \
HF_DATASETS_CACHE="$DERIVED/cache/huggingface/datasets" \
PYTHONPATH="$ROOT_DIR/tools" "$PYTHON" "$ROOT_DIR/tools/act_jsonl_to_lerobot.py" \
  --input-jsonl "$ACT_DIR/episode_000000.jsonl" \
  --output-dir "$LEROBOT_DIR" \
  --repo-id local/icra2027-precision-alignment-smoke \
  --task "precision alignment"

echo "[DONE] smoke output: $DERIVED"
echo "[NOTE] conversion-smoke-audit.json is synthetic and must never be used as a task-success label."
