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
    parser.add_argument("--kind", choices=("act", "filter", "imle"), required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--dataset-stats", type=Path)
    parser.add_argument("--imle-root", type=Path)
    args = parser.parse_args()

    if args.kind == "act" and args.dataset_stats is None:
        raise ValueError("ACT promotion requires --dataset-stats from the training dataset")

    checkpoint = args.checkpoint.expanduser().resolve()
    if not checkpoint.exists() or not checkpoint.is_file() and not checkpoint.is_dir():
        raise ValueError(f"checkpoint not found: {checkpoint}")
    output = args.output.expanduser().resolve()
    if output.exists():
        raise ValueError(f"refusing to overwrite runtime config: {output}")
    default_name = {
        "act": "act.yaml",
        "filter": "learned_filter.yaml",
        "imle": "imle.yaml",
    }[args.kind]
    default_template = ROOT / "config/runtime" / default_name
    template = (args.template or default_template).expanduser().resolve()
    config = yaml.safe_load(template.read_text(encoding="utf-8")) or {}
    expected_schema = {
        "act": "robot_teleop.act-runtime/v1",
        "filter": "robot_teleop.learned-filter-runtime/v1",
        "imle": "robot_teleop.imle-runtime/v1",
    }[args.kind]
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
    if args.kind == "imle" and args.imle_root is not None:
        imle_root = args.imle_root.expanduser().resolve()
        if not (imle_root / "src" / "robot_policy_imle").is_dir():
            raise ValueError(f"IMLE source not found under: {imle_root}")
        config["imle_root"] = str(imle_root)
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
