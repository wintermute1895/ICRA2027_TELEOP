#!/usr/bin/env python3
"""Read-only export and quality evaluation for one model rollout bag."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def resolve(value: str | Path, base: Path = ROOT) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def bag_path(value: Path) -> Path:
    path = value.expanduser().resolve()
    if (path / "metadata.yaml").is_file():
        return path
    candidate = path / "artifacts" / "rosbag2"
    if (candidate / "metadata.yaml").is_file():
        return candidate
    raise ValueError(f"rosbag metadata not found under: {path}")


def camera_args(config: dict[str, Any], overrides: list[str]) -> list[str]:
    cameras = overrides or [
        f"{item['id']}={str(item['namespace']).rstrip('/')}"
        for item in config.get("cameras", [])
        if item.get("id") and item.get("namespace")
    ]
    if not cameras:
        raise ValueError("no cameras configured; add cameras to rollout YAML or use --camera ID=NS")
    result: list[str] = []
    for index, spec in enumerate(cameras):
        if "=" not in spec:
            raise ValueError(f"--camera expects ID=NS: {spec}")
        camera_id, namespace = spec.split("=", 1)
        if not camera_id or not namespace.startswith("/"):
            raise ValueError(f"invalid camera mapping: {spec}")
        result += (["--camera-namespace"] if index == 0 else ["--extra-camera-namespace"])
        result += [namespace, "--camera-id", camera_id]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "config/runtime/rollout.yaml")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--source-domain", choices=("real", "sim"), default="real")
    parser.add_argument("--arm", choices=("left", "right"))
    parser.add_argument("--robot-namespace")
    parser.add_argument("--teleop-namespace", default="/teleop")
    parser.add_argument("--camera", action="append", default=[])
    parser.add_argument("--max-camera-age-ms", type=float)
    parser.add_argument("--max-command-age-ms", type=float)
    args = parser.parse_args()

    config_path = resolve(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if config.get("schema") != "robot_teleop.rollout/v1":
        raise ValueError(f"unsupported rollout config schema: {config.get('schema')}")
    bag = bag_path(args.bag)
    arm = args.arm or str(config.get("arm", "right"))
    if arm not in {"left", "right"}:
        raise ValueError(f"invalid rollout arm: {arm}")
    output = resolve(args.output_dir) if args.output_dir else Path(str(bag) + ".evaluation")
    if output.exists():
        raise ValueError(f"refusing to overwrite: {output}")
    output.mkdir(parents=True)
    export = output / "export" / "episode.jsonl"
    quality = output / "reports" / "data_quality.json"
    trajectory = output / "reports" / "trajectory_quality.json"
    export.parent.mkdir(parents=True)
    quality.parent.mkdir(parents=True)

    evaluation = config.get("evaluation") or {}
    max_camera_age = float(args.max_camera_age_ms if args.max_camera_age_ms is not None else evaluation.get("max_camera_age_ms", 100.0))
    max_command_age = float(args.max_command_age_ms if args.max_command_age_ms is not None else evaluation.get("max_command_age_ms", 100.0))
    command = [
        "/usr/bin/python3", str(ROOT / "tools/export_rosbag_episode.py"),
        "--bag", str(bag), "--output", str(export), "--arm", arm,
        "--source-domain", args.source_domain, "--teleop-namespace", args.teleop_namespace,
        "--max-camera-age-ms", str(max_camera_age), "--max-command-age-ms", str(max_command_age),
        *camera_args(config, args.camera),
    ]
    if args.robot_namespace:
        command += ["--robot-namespace", args.robot_namespace]
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)

    data_result = subprocess.run([
        "/usr/bin/python3", str(ROOT / "tools/score_episode_data_quality.py"),
        "--episode", str(export), "--output", str(quality),
    ], check=False)
    trajectory_result = subprocess.run([
        "/usr/bin/python3", str(ROOT / "tools/evaluate_trajectory_quality.py"),
        "--episode", str(export), "--output", str(trajectory),
    ], check=False)
    payload = {
        "schema": "robot_teleop.rollout-evaluation/v1",
        "bag": str(bag),
        "config": str(config_path),
        "arm": arm,
        "data_quality_exit": data_result.returncode,
        "trajectory_quality_exit": trajectory_result.returncode,
        "data_quality_report": str(quality),
        "trajectory_quality_report": str(trajectory),
        "evaluation_mode": "offline_read_only",
        "hardware_accessed": False,
    }
    (output / "rollout_evaluation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if data_result.returncode == 0 and trajectory_result.returncode == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, yaml.YAMLError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"[FATAL] {error}") from error
