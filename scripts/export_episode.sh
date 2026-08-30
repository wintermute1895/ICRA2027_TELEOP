#!/usr/bin/env bash
# Convert one completed ROS2 bag into derived episode/v1 left/right JSONL and quality reports.
# Offline only: no ROS node is created and no robot, hand, or SDK API is called.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BAG=""
OUTPUT_DIR=""
SOURCE_DOMAIN=""
ROBOT_NAMESPACE=""
CAMERA_NAMESPACE=""
EXTRA_CAMERA_NAMESPACES=()
CAMERA_IDS=()
TELEOP_NAMESPACE="/teleop"

usage() {
  cat >&2 <<'EOF'
Usage: scripts/export_episode.sh --bag BAG_DIR --source-domain real|sim --output-dir DIR [options]

Options:
  --robot-namespace NS   override /robot1 or /sim/robot1
  --camera-namespace NS  override /camera/camera or /sim/camera/camera
  --extra-camera-namespace NS  add another camera namespace (repeatable)
  --camera-id ID         camera id in namespace order (repeatable)
  --teleop-namespace NS  mapped-command namespace (default: /teleop; historical bags: /vist)
EOF
}

while (($#)); do
  case "$1" in
    --bag) BAG="${2:-}"; shift 2 ;;
    --source-domain) SOURCE_DOMAIN="${2:-}"; shift 2 ;;
    --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
    --robot-namespace) ROBOT_NAMESPACE="${2:-}"; shift 2 ;;
    --camera-namespace) CAMERA_NAMESPACE="${2:-}"; shift 2 ;;
    --extra-camera-namespace) EXTRA_CAMERA_NAMESPACES+=("${2:-}"); shift 2 ;;
    --camera-id) CAMERA_IDS+=("${2:-}"); shift 2 ;;
    --teleop-namespace) TELEOP_NAMESPACE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ -d "$BAG" ]] || { echo "bag directory not found: $BAG" >&2; exit 2; }
[[ "$SOURCE_DOMAIN" =~ ^(real|sim)$ ]] || { echo "--source-domain must be real or sim" >&2; exit 2; }
[[ -n "$OUTPUT_DIR" ]] || { echo "--output-dir is required" >&2; exit 2; }
[[ -f /opt/ros/humble/setup.bash ]] || { echo "ROS2 Humble is not installed" >&2; exit 2; }

set +u
source /opt/ros/humble/setup.bash
set -u

mkdir -p "$OUTPUT_DIR"
COMMON=(--bag "$BAG" --source-domain "$SOURCE_DOMAIN" --teleop-namespace "$TELEOP_NAMESPACE")
[[ -z "$ROBOT_NAMESPACE" ]] || COMMON+=(--robot-namespace "$ROBOT_NAMESPACE")
[[ -z "$CAMERA_NAMESPACE" ]] || COMMON+=(--camera-namespace "$CAMERA_NAMESPACE")
for namespace in "${EXTRA_CAMERA_NAMESPACES[@]}"; do COMMON+=(--extra-camera-namespace "$namespace"); done
for camera_id in "${CAMERA_IDS[@]}"; do COMMON+=(--camera-id "$camera_id"); done

for arm in left right; do
  episode="$OUTPUT_DIR/${arm}_episode.jsonl"
  report="$OUTPUT_DIR/${arm}_data_quality.json"
  [[ ! -e "$episode" && ! -e "$report" ]] || {
    echo "refusing to overwrite existing output for ${arm}: $OUTPUT_DIR" >&2
    exit 2
  }
  PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 "$ROOT_DIR/tools/export_rosbag_episode.py" \
    "${COMMON[@]}" --arm "$arm" --output "$episode"
  set +e
  /usr/bin/python3 "$ROOT_DIR/tools/score_episode_data_quality.py" \
    --episode "$episode" --output "$report"
  score_status=$?
  set -e
  [[ -s "$report" ]] || exit "$score_status"
done

echo "Offline export complete: $OUTPUT_DIR"
echo "A quality_gate=review is preserved for inspection; it does not delete source data."
