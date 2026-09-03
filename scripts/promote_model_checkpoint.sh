#!/usr/bin/env bash
# Create a new immutable ACT/filter runtime config from a checkpoint.
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec /usr/bin/python3 "$ROOT_DIR/tools/promote_runtime_model.py" "$@"
