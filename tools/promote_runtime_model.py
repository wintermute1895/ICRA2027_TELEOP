#!/usr/bin/env python3
"""Create an immutable runtime config for a promoted local checkpoint."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

try:
    from model_artifacts import sha256_path
except ImportError:  # package import from repository tests
    from tools.model_artifacts import sha256_path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("act", "filter"), required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--dataset-stats", type=Path)
    args = parser.parse_args()

    if args.kind == "act" and args.dataset_stats is None:
        raise ValueError("ACT promotion requires --dataset-stats from the training dataset")

    checkpoint = args.checkpoint.expanduser().resolve()
    if not checkpoint.exists() or not checkpoint.is_file() and not checkpoint.is_dir():
        raise ValueError(f"checkpoint not found: {checkpoint}")
    output = args.output.expanduser().resolve()
    if output.exists():
        raise ValueError(f"refusing to overwrite runtime config: {output}")
    default_template = ROOT / "config/runtime" / ("act.yaml" if args.kind == "act" else "learned_filter.yaml")
    template = (args.template or default_template).expanduser().resolve()
    config = yaml.safe_load(template.read_text(encoding="utf-8")) or {}
    expected_schema = "robot_teleop.act-runtime/v1" if args.kind == "act" else "robot_teleop.learned-filter-runtime/v1"
    if config.get("schema") != expected_schema:
        raise ValueError(f"template schema does not match {args.kind}: {template}")
    config["enabled"] = True
    config["checkpoint"] = str(checkpoint)
    config["checkpoint_sha256"] = sha256_path(checkpoint)
    if args.kind == "act" and args.dataset_stats:
        stats = args.dataset_stats.expanduser().resolve()
        if not stats.is_file():
            raise ValueError(f"dataset stats not found: {stats}")
        config["dataset_stats"] = str(stats)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    print(f"[READY] {args.kind} runtime config: {output}")
    print(f"[INFO] checkpoint_sha256: {config['checkpoint_sha256']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise SystemExit(f"[FATAL] {error}") from error
