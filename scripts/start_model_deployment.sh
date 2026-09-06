#!/usr/bin/env bash
# Start the single ACT/filter deployment boundary. Shadow is the default.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT_DIR/config/runtime/model_deployment.yaml"
MODE="shadow"
CONFIRM=""
SOURCE=""
FILTER_CONFIG=""
ACT_CONFIG=""
POSITIONAL_SET=0
while (($#)); do
  case "$1" in
    --config=*) CONFIG="${1#*=}"; shift ;;
    --config) CONFIG="${2:-}"; shift 2 ;;
    --active) MODE="active"; shift ;;
    --shadow) MODE="shadow"; shift ;;
    --source=*) SOURCE="${1#*=}"; shift ;;
    --source) SOURCE="${2:-}"; shift 2 ;;
    --filter-config=*) FILTER_CONFIG="${1#*=}"; shift ;;
    --filter-config) FILTER_CONFIG="${2:-}"; shift 2 ;;
    --act-config=*) ACT_CONFIG="${1#*=}"; shift ;;
    --act-config) ACT_CONFIG="${2:-}"; shift 2 ;;
    --confirm=*) CONFIRM="${1#*=}"; shift ;;
    --confirm) CONFIRM="${2:-}"; shift 2 ;;
    --help|-h) echo "usage: $0 [CONFIG] [--source teleop|filter|act|hybrid] [--filter-config PATH] [--act-config PATH] [--shadow|--active --confirm I_UNDERSTAND_MODEL_DEPLOYMENT]"; exit 0 ;;
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
if [[ "$MODE" == active && "$CONFIRM" != I_UNDERSTAND_MODEL_DEPLOYMENT ]]; then
  echo "[FATAL] active deployment requires --confirm=I_UNDERSTAND_MODEL_DEPLOYMENT" >&2
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
  --config "$CONFIG" --mode "$MODE")
[[ -n "$SOURCE" ]] && CMD+=(--source "$SOURCE")
[[ -n "$CONFIRM" ]] && CMD+=(--confirm "$CONFIRM")
"${CMD[@]}"
