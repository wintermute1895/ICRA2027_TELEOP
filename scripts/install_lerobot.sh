#!/usr/bin/env bash
# Install LeRobot into the dedicated teleop-train Conda environment.
# No sudo and no system Python changes are performed.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/training_env.sh"
CONDA="$(resolve_conda_bin)" || { echo "[FATAL] Conda was not found; install Miniconda or Miniforge first" >&2; exit 2; }
ENV_PREFIX="$(resolve_training_env_prefix)" || { echo "[FATAL] cannot resolve the training environment" >&2; exit 2; }
if [[ ! -x "$ENV_PREFIX/bin/python" ]]; then
  echo "[INFO] creating ${LEROBOT_ENV_NAME:-teleop-train} with Python 3.11"
  "$CONDA" create --yes --name "${LEROBOT_ENV_NAME:-teleop-train}" python=3.11 pip
fi
PYTHON="${ENV_PREFIX}/bin/python"
PIP="${ENV_PREFIX}/bin/pip"
INDEX_URL="${LEROBOT_PYPI_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"

[[ -x "$PYTHON" ]] || { echo "[FATAL] Python environment not found: $ENV_PREFIX" >&2; exit 2; }
[[ -x "$PIP" ]] || { echo "[FATAL] pip not found: $PIP" >&2; exit 2; }

echo "[INFO] environment: $ENV_PREFIX"
echo "[INFO] index: $INDEX_URL"
echo "[INFO] requirements: $ROOT_DIR/requirements-training.txt"

PIP_DISABLE_PIP_VERSION_CHECK=1 \
  "$PIP" install \
    --index-url "$INDEX_URL" \
    --timeout 180 \
    --retries 10 \
    --prefer-binary \
    --no-cache-dir \
    --requirement "$ROOT_DIR/requirements-training.txt"

"$PYTHON" - <<'PY'
import importlib.metadata as metadata
import importlib.util
import sys

if importlib.util.find_spec("lerobot") is None:
    raise SystemExit("lerobot import failed")
print(f"[PASS] lerobot {metadata.version('lerobot')} imported with Python {sys.version.split()[0]}")
for name in ("torch", "cv2", "numpy"):
    if importlib.util.find_spec(name) is None:
        raise SystemExit(f"required dependency missing after install: {name}")
    print(f"[PASS] {name} import available")
PY

echo "[DONE] LeRobot installation completed in $ENV_PREFIX"
