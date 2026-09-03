#!/usr/bin/env bash
# Start ACT's GPU worker and ROS candidate adapter. No bridge is touched here.
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-$ROOT_DIR/config/runtime/act.yaml}"
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  echo "usage: $0 [config/runtime/act.yaml]"
  exit 0
fi
source "$ROOT_DIR/scripts/lib/training_env.sh"
ENV_PREFIX="$(resolve_training_env_prefix)" || { echo "[FATAL] teleop-train is unavailable" >&2; exit 2; }
SOCKET="$($ENV_PREFIX/bin/python - "$CONFIG" <<'PY'
import sys, yaml
c=yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
if c.get("enabled") is not True: raise SystemExit("[FATAL] ACT runtime is disabled")
print(c["socket"])
PY
)"
"$ENV_PREFIX/bin/python" "$ROOT_DIR/tools/act_worker.py" --config "$CONFIG" &
WORKER_PID=$!
trap 'kill "$WORKER_PID" 2>/dev/null || true; wait "$WORKER_PID" 2>/dev/null || true' EXIT INT TERM
for _ in {1..100}; do
  [[ -S "$SOCKET" ]] && break
  kill -0 "$WORKER_PID" 2>/dev/null || { echo "[FATAL] ACT worker exited" >&2; exit 2; }
  sleep 0.1
done
[[ -S "$SOCKET" ]] || { echo "[FATAL] ACT worker did not become ready" >&2; exit 2; }
bash "$ROOT_DIR/skills/ros2-python-env/scripts/run_ros2_python.sh" \
  /usr/bin/python3 "$ROOT_DIR/tools/act_ros_adapter.py" --config "$CONFIG"
