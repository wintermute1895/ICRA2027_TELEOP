#!/usr/bin/env python3
"""Resolve versioned experiment profiles into one immutable capture manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def read_yaml(path: Path, expected_schema: str, ancestry: tuple[Path, ...] = ()) -> tuple[dict[str, Any], dict[str, str]]:
    resolved = path if path.is_absolute() else ROOT / path
    resolved = resolved.resolve()
    if resolved in ancestry:
        chain = " -> ".join(str(item) for item in (*ancestry, resolved))
        raise SystemExit(f"cyclic profile inheritance: {chain}")
    data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != expected_schema:
        raise SystemExit(f"unexpected schema in {resolved}; expected {expected_schema}")
    hashes = {str(resolved.relative_to(ROOT)): hashlib.sha256(resolved.read_bytes()).hexdigest()}
    parent = data.get("extends")
    if parent is None:
        return data, hashes
    parent_data, parent_hashes = read_yaml(Path(parent), expected_schema, (*ancestry, resolved))
    return deep_merge(parent_data, data), parent_hashes | hashes


def uniform_vector(rng: random.Random, limits: list[float]) -> list[float]:
    return [rng.uniform(-float(limit), float(limit)) for limit in limits]


def split_for_seed(contract: dict[str, Any], seed: int) -> str:
    for name, bounds in (("train", contract["train_seeds"]), ("validation", contract["validation_seeds"]), ("held_out", contract["held_out_seeds"])):
        if int(bounds[0]) <= seed <= int(bounds[1]):
            return name
    raise SystemExit(f"trial seed {seed} is outside the declared split contract")


def perturbation(task: dict[str, Any], seed: int, pose_level: str, occlusion_level: str, camera_level: str, contact_level: str) -> dict[str, Any]:
    profile = task["perturbation_profile"]
    try:
        pose, occlusion, camera, contact = (
            profile["target_pose_levels"][pose_level], profile["occlusion_levels"][occlusion_level],
            profile["camera_bias_levels"][camera_level], profile["contact_bias_levels"][contact_level],
        )
    except KeyError as exc:
        raise SystemExit(f"unknown perturbation level: {exc.args[0]}") from exc
    rng = random.Random(seed)
    return {
        "trial_seed": seed,
        "split": split_for_seed(task["split_contract"], seed),
        "target_pose": {"level": pose_level, "translation_m": uniform_vector(rng, pose["translation_m"]), "rotation_deg": uniform_vector(rng, pose["rotation_deg"])},
        "occlusion": {"level": occlusion_level, "duration_s": float(occlusion["duration_s"]), "active": rng.random() < float(occlusion["probability"])},
        "camera_bias": {"level": camera_level, "translation_m": uniform_vector(rng, [camera["translation_m"]] * 3), "rotation_deg": uniform_vector(rng, [camera["rotation_deg"]] * 3)},
        "contact_bias": {"level": contact_level, "lateral_m": uniform_vector(rng, [contact["lateral_m"]] * 2), "angular_deg": uniform_vector(rng, [contact["angular_deg"]] * 2)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", type=Path, required=True)
    parser.add_argument("--task", type=Path, default=Path("config/tasks/usb_c_insertion_v1.yaml"))
    parser.add_argument("--evaluation", type=Path, default=Path("config/evaluation/precision_assembly_v1.yaml"))
    parser.add_argument("--domain", choices=("sim", "real"), required=True)
    parser.add_argument("--trial-seed", type=int, required=True)
    parser.add_argument("--target-pose-level", default="medium")
    parser.add_argument("--occlusion-level", default="brief")
    parser.add_argument("--camera-bias-level", default="mild")
    parser.add_argument("--contact-bias-level", default="mild")
    parser.add_argument("--experiment-id", default="precision_assembly_exploratory_v1")
    parser.add_argument("--operator-id", default="anonymous")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    condition, condition_hash = read_yaml(args.condition, "robot_teleop.condition-profile/v1")
    task, task_hash = read_yaml(args.task, "robot_teleop.task-profile/v1")
    evaluation, evaluation_hash = read_yaml(args.evaluation, "robot_teleop.evaluation-profile/v1")
    reference, reference_hash = read_yaml(Path(condition["reference_profile"]), "robot_teleop.reference-profile/v1")
    safety, safety_hash = read_yaml(Path(condition["safety_profile"]), "robot_teleop.safety-profile/v1")
    inputs = condition_hash | task_hash | evaluation_hash | reference_hash | safety_hash
    resolved = {
        "schema": "robot_teleop.experiment-manifest/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": args.experiment_id,
        "domain": args.domain,
        "condition_id": condition["condition_id"],
        "condition_role": condition["condition_role"],
        "task_id": task["task_id"],
        "task_revision": task["task_revision"],
        "reference_revision": reference["reference_revision"],
        "policy_id": condition["policy_profile"]["policy_id"],
        "policy_revision": condition["policy_profile"]["policy_revision"],
        "safety_id": safety["safety_id"],
        "evaluation_id": evaluation["evaluation_id"],
        "operator_id": args.operator_id,
        "perturbation": perturbation(task, args.trial_seed, args.target_pose_level, args.occlusion_level, args.camera_bias_level, args.contact_bias_level),
        "profile_sha256": inputs,
        "immutable_fields": ["condition_id", "task_revision", "reference_revision", "policy_revision", "safety_id", "evaluation_id", "perturbation", "profile_sha256"],
    }
    identity = {key: value for key, value in resolved.items() if key != "created_at"}
    resolved["manifest_id"] = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite immutable manifest: {args.output}")
    args.output.write_text(json.dumps(resolved, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "manifest_id": resolved["manifest_id"], "condition_id": resolved["condition_id"], "split": resolved["perturbation"]["split"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
