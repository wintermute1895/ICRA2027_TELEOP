#!/usr/bin/env python3
"""Run one reproducible visual residual-filter training round from YAML.

The round config is the public entry point; this wrapper only orchestrates the
existing validated trainer/evaluator and never reads ROS or mutates source data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
def paths(values: list[str], base: Path) -> list[Path]:
    result = [Path(v) for v in values]
    return [p if p.is_absolute() else (base / p).resolve() for p in result]


def resolve_config_path(value: str, base: Path) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    candidate = (base / p).resolve()
    return candidate if candidate.exists() else (ROOT / p).resolve()


def next_output_dir(path: Path, policy: str) -> Path:
    if not path.exists() or policy == "overwrite":
        return path
    if policy == "error":
        raise SystemExit(f"refusing to overwrite output: {path}")
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.name}_r{index:02d}")
        if not candidate.exists():
            return candidate
    raise SystemExit(f"too many existing output rounds: {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    args = ap.parse_args()
    config_path = args.config.resolve()
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    dataset = cfg.get("dataset") or {}
    train = paths(dataset.get("train", []), config_path.parent)
    validation = paths(dataset.get("validation", []), config_path.parent)
    if not train or any(not p.is_file() for p in train + validation):
        missing = [str(p) for p in train + validation if not p.is_file()]
        raise SystemExit("missing filter-training episode(s): " + ", ".join(missing))
    output_cfg = cfg.get("output") or {}
    out = Path(output_cfg.get("directory", "runs/filter/round"))
    out = out if out.is_absolute() else resolve_config_path(str(out), config_path.parent)
    out = next_output_dir(out, str(output_cfg.get("on_exists", "increment")))
    model_config = resolve_config_path(str(cfg.get("training", {}).get("model_config", "config/filters/trajectory_cvae_transformer_v0_2_vlm.yaml")), config_path.parent)
    training = cfg.get("training") or {}
    train_cmd = [sys.executable, str(ROOT / "tools/train_trajectory_filter.py"), "--config", str(model_config), "--output-dir", str(out / "model"), "--device", str(training.get("device", "cuda"))]
    if training.get("require_cuda", True): train_cmd.append("--require-cuda")
    tensorboard = training.get("tensorboard_logdir", str(out / "tensorboard"))
    configured_out = Path(str(output_cfg.get("directory", out)))
    if tensorboard and configured_out != out and str(tensorboard).startswith(str(configured_out)):
        tensorboard = str(out) + str(tensorboard)[len(str(configured_out)):]
    if tensorboard:
        tb = resolve_config_path(str(tensorboard), config_path.parent)
        train_cmd += ["--tensorboard-logdir", str(tb)]
    for key in ("epochs", "batch_size", "learning_rate", "seed", "validation_fraction"):
        if key in training: train_cmd += [f"--{key.replace('_', '-')}", str(training[key])]
    for p in train: train_cmd += ["--episode", str(p)]
    for p in validation: train_cmd += ["--validation-episode", str(p)]
    out.mkdir(parents=True)
    subprocess.run(train_cmd, check=True)
    eval_cfg = cfg.get("evaluation") or {}
    eval_eps = validation or train
    eval_cmd = [sys.executable, str(ROOT / "tools/evaluate_trajectory_filter.py"), "--checkpoint", str(out / "model/trajectory_filter.pt"), "--output-dir", str(out / "evaluation"), "--device", str(eval_cfg.get("device", training.get("device", "cuda")))]
    for p in eval_eps: eval_cmd += ["--episode", str(p)]
    subprocess.run(eval_cmd, check=True)
    manifest = {"schema": "robot_teleop.filter-round/v0.1", "config": str(config_path), "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(), "train": [str(p) for p in train], "validation": [str(p) for p in validation], "output": str(out), "checkpoint": str(out / "model/trajectory_filter.pt"), "evaluation": str(out / "evaluation/evaluation_report.json")}
    (out / "round_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
