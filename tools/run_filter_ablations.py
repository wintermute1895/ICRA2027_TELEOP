#!/usr/bin/env python3
"""Run a fixed-budget filter ablation matrix.

The runner owns only experiment orchestration.  Training and evaluation remain
in their existing scripts, so every variant uses the same data and seed.
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

import yaml


VARIANTS = {
    "full": {},
    "no_visual": {"model": {"visual_dim": 0, "gain_enabled": True}},
    "no_gain": {"model": {"gain_enabled": False}, "loss": {"gain_weight": 0.0}},
    "fixed_gain": {"model": {"gain_enabled": True, "fixed_gain": 0.25}, "loss": {"gain_weight": 0.0}},
    "shared_head": {"model": {"shared_action_gain_head": True}},
    "nominal_only": {"loss": {"correction_weight": 0.0, "gain_weight": 0.0}},
    "correction_only": {"loss": {"zero_weight": 0.0}},
    "single_step": {"model": {"horizon": 1}},
    "no_rate_limit": {"model": {"alpha_rate": 1.0}},
}


def merge(base: dict, patch: dict) -> dict:
    result = copy.deepcopy(base)
    for section, values in patch.items():
        result.setdefault(section, {}).update(values)
    return result


def run(cmd: list[str], log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        subprocess.run(cmd, stdout=stream, stderr=subprocess.STDOUT, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--episode", type=Path, action="append", required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--variant", choices=[*VARIANTS, "all"], default="all")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    base = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    names = list(VARIANTS) if args.variant == "all" else [args.variant]
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    summary = []
    for name in names:
        out = root / name
        model_dir, eval_dir = out / "model", out / "evaluation"
        config_path = out / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(merge(base, VARIANTS[name]), sort_keys=False), encoding="utf-8")
        train = [sys.executable, str(Path(__file__).with_name("train_trajectory_filter.py")),
                 "--config", str(config_path), "--output-dir", str(model_dir),
                 "--epochs", str(args.epochs), "--batch-size", str(args.batch_size),
                 "--device", args.device, "--seed", str(args.seed)]
        for episode in args.episode:
            train += ["--episode", str(episode)]
        try:
            run(train, out / "train.log")
            evaluate = [sys.executable, str(Path(__file__).with_name("evaluate_trajectory_filter.py")),
                        "--checkpoint", str(model_dir / "trajectory_filter.pt"),
                        "--output-dir", str(eval_dir), "--device", args.device]
            for episode in args.episode:
                evaluate += ["--episode", str(episode)]
            run(evaluate, out / "evaluate.log")
            report = json.loads((eval_dir / "evaluation_report.json").read_text(encoding="utf-8"))
            summary.append({"variant": name, "status": "ok", "evaluation": report.get("aggregate", {})})
        except subprocess.CalledProcessError as error:
            summary.append({"variant": name, "status": "failed", "returncode": error.returncode})
    (root / "ablation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(root / "ablation_summary.json"), "variants": summary}, indent=2))
    return 0 if all(item["status"] == "ok" for item in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
