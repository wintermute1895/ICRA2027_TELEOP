#!/usr/bin/env bash
# Start the single active ACT/filter deployment boundary.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Keep ROS node logs on a mounted data disk; the default ~/.ros/log lives on
# the small system disk and grows during long deployments. Fall back through
# candidates so a missing/unwritable disk never blocks deployment.
if [[ -z "${ROS_LOG_DIR:-}" ]]; then
  for candidate in \
    "/media/${USER:-$(id -un)}/Cyan_data/ICRA2027_DATA/ros_logs" \
    "/media/${USER:-$(id -un)}/robot_data/ICRA2027_Data/ros_logs" \
    "/tmp/teleop_ros_logs"; do
    if mkdir -p "$candidate" 2>/dev/null; then
      ROS_LOG_DIR="$candidate"
      break
    fi
  done
fi
export ROS_LOG_DIR
mkdir -p "$ROS_LOG_DIR"
CONFIG="$ROOT_DIR/config/runtime/model_deployment.yaml"
CONFIRM=""
SOURCE=""
FILTER_CONFIG=""
ACT_CONFIG=""
POSITIONAL_SET=0
while (($#)); do
  case "$1" in
    --config=*) CONFIG="${1#*=}"; shift ;;
    --config) CONFIG="${2:-}"; shift 2 ;;
    --source=*) SOURCE="${1#*=}"; shift ;;
    --source) SOURCE="${2:-}"; shift 2 ;;
    --filter-config=*) FILTER_CONFIG="${1#*=}"; shift ;;
    --filter-config) FILTER_CONFIG="${2:-}"; shift 2 ;;
    --act-config=*) ACT_CONFIG="${1#*=}"; shift ;;
    --act-config) ACT_CONFIG="${2:-}"; shift 2 ;;
    --confirm=*) CONFIRM="${1#*=}"; shift ;;
    --confirm) CONFIRM="${2:-}"; shift 2 ;;
    --help|-h) echo "usage: $0 [CONFIG] --confirm I_UNDERSTAND_MODEL_DEPLOYMENT [--source teleop|filter|act|hybrid] [--filter-config PATH] [--act-config PATH]"; exit 0 ;;
    /*|*.yaml)
      (( POSITIONAL_SET == 0 )) || { echo "only one config path is allowed" >&2; exit 2; }
      CONFIG="$1"; POSITIONAL_SET=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$CONFIG" == /* ]] || CONFIG="$ROOT_DIR/$CONFIG"
[[ -z "$FILTER_CONFIG" || "$FILTER_CONFIG" == /* ]] || FILTER_CONFIG="$ROOT_DIR/$FILTER_CONFIG"
[[ -z "$ACT_CONFIG" || "$ACT_CONFIG" == /* ]] || ACT_CONFIG="$ROOT_DIR/$ACT_CONFIG"
[[ -f "$CONFIG" ]] || { echo "[FATAL] config not found: $CONFIG" >&2; exit 2; }
if [[ "$CONFIRM" != I_UNDERSTAND_MODEL_DEPLOYMENT ]]; then
  echo "[FATAL] active model deployment requires --confirm=I_UNDERSTAND_MODEL_DEPLOYMENT" >&2
  exit 3
fi

PIDS=()
cleanup() { for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM
if [[ -n "$FILTER_CONFIG" ]]; then
  [[ "$SOURCE" == "filter" || -z "$SOURCE" ]] && SOURCE=filter
  bash "$ROOT_DIR/scripts/start_learned_filter.sh" "$FILTER_CONFIG" & PIDS+=("$!")
fi
if [[ -n "$ACT_CONFIG" ]]; then
  [[ "$SOURCE" == "act" || -z "$SOURCE" ]] && SOURCE=act
  bash "$ROOT_DIR/scripts/start_act_adapter.sh" "$ACT_CONFIG" & PIDS+=("$!")
fi

CMD=(bash "$ROOT_DIR/skills/ros2-python-env/scripts/run_ros2_python.sh"
  /usr/bin/python3 "$ROOT_DIR/tools/model_deployment_supervisor.py"
  --config "$CONFIG")
[[ -n "$SOURCE" ]] && CMD+=(--source "$SOURCE")
"${CMD[@]}"
