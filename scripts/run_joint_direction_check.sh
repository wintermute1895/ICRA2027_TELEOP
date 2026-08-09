#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONDA_ENV="${TELEOP_CONDA_ENV:-mpc_env}"
export PYTHONDONTWRITEBYTECODE=1
if ! command -v conda >/dev/null 2>&1; then echo "conda is required" >&2; exit 2; fi
conda run -n "${CONDA_ENV}" python "${ROOT_DIR}/scripts/check_teleop_environment.py" --mode python
exec conda run --no-capture-output -n "${CONDA_ENV}" python "${ROOT_DIR}/tools/check_joint_directions.py" "$@"
