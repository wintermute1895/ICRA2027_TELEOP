#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONDA_ENV="${TELEOP_CONDA_ENV:-mpc_env}"
PORT="${TELEOP_UDP_PORT:-5005}"
HEADLESS=0
if [[ "${1:-}" == "--headless" ]]; then HEADLESS=1; shift; fi
if ! command -v conda >/dev/null 2>&1; then echo "conda is required" >&2; exit 2; fi
conda run -n "${CONDA_ENV}" python "${ROOT_DIR}/scripts/check_teleop_environment.py" --mode python
CONTROL_ARGS=("${ROOT_DIR}/IROS_teleop/control_anyteleop.py" --udp-port "${PORT}")
if (( HEADLESS )); then CONTROL_ARGS+=(--no-viewer); fi
conda run --no-capture-output -n "${CONDA_ENV}" python "${CONTROL_ARGS[@]}" &
CONTROL_PID=$!
cleanup() { kill "${CONTROL_PID}" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 130' INT TERM
sleep 2
conda run --no-capture-output -n "${CONDA_ENV}" python "${ROOT_DIR}/IROS_teleop/mock_vision.py" --port "${PORT}"
wait "${CONTROL_PID}"
