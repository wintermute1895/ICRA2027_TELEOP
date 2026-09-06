#!/usr/bin/env bash
# Validate an ACT arm7 runtime config without importing LeRobot or CUDA.
# Usage: bash scripts/validate_act_deployment.sh [config/runtime/act-button-A.yaml]
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-$ROOT_DIR/config/runtime/act-button-A.yaml}"
[[ -f "$CONFIG" ]] || { echo "[FATAL] config not found: $CONFIG" >&2; exit 2; }

/usr/bin/python3 - "$CONFIG" "$ROOT_DIR/tools" <<'PY'
import sys
from pathlib import Path
import yaml

sys.path.insert(0, sys.argv[2])
from act_arm7_contract import validate_runtime_config
from model_artifacts import sha256_path

config_path = Path(sys.argv[1]).resolve()
config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
if config.get("enabled") is not True:
    raise SystemExit(f"[FATAL] ACT runtime is disabled: {config_path}")
validate_runtime_config(config)

checkpoint = Path(str(config["checkpoint"])).expanduser().resolve()
if not checkpoint.exists():
    raise SystemExit(f"[FATAL] checkpoint not found: {checkpoint}")
expected = str(config.get("checkpoint_sha256") or "")
actual = sha256_path(checkpoint)
if not expected or actual != expected:
    raise SystemExit(f"[FATAL] checkpoint_sha256 mismatch\n  expected={expected}\n  actual  ={actual}")

stats = Path(str(config["dataset_stats"])).expanduser().resolve()
if not stats.is_file():
    raise SystemExit(f"[FATAL] dataset_stats not found: {stats}")

print(f"[READY] ACT arm7 deployment validated: {config_path}")
print(f"  checkpoint = {checkpoint}")
print(f"  sha256     = {actual}")
print(f"  stats      = {stats}")
PY
