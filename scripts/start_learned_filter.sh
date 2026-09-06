#!/usr/bin/env bash
# Start the GPU worker and ROS adapter. The hardware bridge remains the final gate.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-$ROOT_DIR/config/runtime/learned_filter.yaml}"
source "$ROOT_DIR/scripts/lib/training_env.sh"
# Drop ROS/system dist-packages from PYTHONPATH so the teleop interpreter uses
# its own numpy/sympy/transformers stack.
export PYTHONPATH=""
ENV_PREFIX="$(resolve_training_env_prefix)" || { echo "[FATAL] teleop-train is unavailable" >&2; exit 2; }

SOCKET="$($ENV_PREFIX/bin/python - "$CONFIG" <<'PY'
import sys, yaml
value = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
if value.get("enabled") is not True:
    raise SystemExit("[FATAL] learned filter is disabled in runtime config")
print(value["socket"])
PY
)"

# Remove a stale socket from a previous run before the worker starts; the
# adapter readiness loop below only watches for the socket file, so a leftover
# file would otherwise trigger an immediate (failed) adapter connection.
rm -f -- "$SOCKET"

"$ENV_PREFIX/bin/python" "$ROOT_DIR/tools/learned_filter_worker.py" --config "$CONFIG" &
WORKER_PID=$!
trap 'kill "$WORKER_PID" 2>/dev/null || true; wait "$WORKER_PID" 2>/dev/null || true' EXIT INT TERM

for _ in {1..600}; do
  [[ -S "$SOCKET" ]] && break
  kill -0 "$WORKER_PID" 2>/dev/null || { echo "[FATAL] model worker exited" >&2; exit 2; }
  sleep 0.2
done
[[ -S "$SOCKET" ]] || { echo "[FATAL] model worker did not become ready" >&2; exit 2; }

bash "$ROOT_DIR/skills/ros2-python-env/scripts/run_ros2_python.sh" \
  /usr/bin/python3 "$ROOT_DIR/tools/learned_filter_ros_adapter.py" --config "$CONFIG"
