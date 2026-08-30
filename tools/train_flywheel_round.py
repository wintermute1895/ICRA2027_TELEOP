#!/usr/bin/env python3
"""Train one reproducible simulation-only causal-filter flywheel round."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ros2_ws/src/sim_robot_driver"))
sys.path.insert(0, str(ROOT / "tools"))

from episode_analysis_common import finite_vector, load_jsonl  # noqa: E402
from sim_robot_driver.causal_filter import build_feature, train_ridge  # noqa: E402


def resolve(config_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (config_path.parent / path).resolve()


def project_entry(config_path: Path, entry: dict[str, Any], temp_dir: Path, index: int) -> list[dict[str, Any]]:
    output = temp_dir / f"episode_{index:04d}.jsonl"
    command = [
        sys.executable, str(ROOT / "tools/canonical_episode_to_filter_jsonl.py"),
        "--manifest", str(resolve(config_path, entry["manifest"])),
        "--control-jsonl", str(resolve(config_path, entry["control_jsonl"])),
        "--commands-jsonl", str(resolve(config_path, entry["commands_jsonl"])),
        "--output", str(output),
    ]
    if entry.get("task_context_jsonl"):
        command += ["--task-context-jsonl", str(resolve(config_path, entry["task_context_jsonl"]))]
    if entry.get("alignment_tolerance_ns") is not None:
        command += ["--alignment-tolerance-ns", str(entry["alignment_tolerance_ns"])]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or "canonical projection failed")
    return load_jsonl(output)


def make_windows(rows: list[dict[str, Any]], history_length: int, context_size: int) -> tuple[list[np.ndarray], list[list[float]], int]:
    joint_count = len(rows[0].get("joint_names", []))
    if joint_count < 1:
        raise ValueError("projected rows lack joint_names")
    commands = [finite_vector(row.get("mapped_joint_command_rad"), joint_count) for row in rows]
    states = [finite_vector(row.get("robot_joint_state_rad"), joint_count) for row in rows]
    targets = [finite_vector(row.get("controller_command_rad"), joint_count) for row in rows]
    contexts = [finite_vector(row.get("filter_context"), context_size) if context_size else None for row in rows]
    features, accepted = [], []
    for index in range(history_length - 1, len(rows)):
        history = commands[index - history_length + 1:index + 1]
        if any(value is None for value in history) or states[index] is None or targets[index] is None:
            continue
        if context_size and contexts[index] is None:
            continue
        features.append(build_feature(history, states[index], joint_count, history_length, contexts[index], context_size))
        accepted.append(targets[index])
    return features, accepted, joint_count


def prediction_metrics(model: Any, features: list[np.ndarray], targets: list[list[float]]) -> dict[str, float | int | None]:
    if not features:
        return {"samples": 0, "mae": None, "rmse": None}
    mean, scale = np.asarray(model.feature_mean), np.asarray(model.feature_scale)
    weights, bias = np.asarray(model.weights), np.asarray(model.bias)
    predictions = np.vstack([weights @ ((feature - mean) / scale) + bias for feature in features])
    error = predictions - np.vstack(targets)
    return {"samples": len(features), "mae": float(np.mean(np.abs(error))), "rmse": float(math.sqrt(np.mean(error * error)))}


def git_revision() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def train_round(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "robot_teleop.filter-flywheel-round/v1":
        raise ValueError("round config schema must be robot_teleop.filter-flywheel-round/v1")
    round_id = config.get("round_id")
    if not isinstance(round_id, str) or not round_id:
        raise ValueError("round_id is required")
    model_config = config.get("model", {})
    history_length = int(model_config.get("history_length", 8))
    context_size, ridge = int(model_config.get("context_size", 0)), float(model_config.get("ridge", 1e-3))
    if history_length < 1 or context_size < 0 or ridge < 0:
        raise ValueError("invalid history_length, context_size, or ridge")
    entries = config.get("episodes")
    if not isinstance(entries, list) or not entries:
        raise ValueError("episodes must be a non-empty list")
    if output_dir.exists():
        raise ValueError(f"refusing to overwrite existing round output: {output_dir}")
    grouped: dict[str, list[dict[str, Any]]] = {"train": [], "validation": []}
    episode_ids: dict[str, list[str]] = {"train": [], "validation": []}
    rejected: list[dict[str, str]] = []
    joint_names: list[str] | None = None
    with tempfile.TemporaryDirectory(prefix="flywheel_projection_") as temporary:
        for index, entry in enumerate(entries):
            split = entry.get("split")
            if split not in grouped:
                raise ValueError("each episode split must be train or validation")
            try:
                rows = project_entry(config_path, entry, Path(temporary), index)
            except (KeyError, ValueError) as exc:
                rejected.append({"manifest": str(entry.get("manifest", "unknown")), "reason": str(exc)})
                continue
            names = rows[0].get("joint_names")
            if joint_names is None:
                joint_names = names
            elif names != joint_names:
                rejected.append({"manifest": str(entry["manifest"]), "reason": "joint_names mismatch"})
                continue
            grouped[split].extend(rows)
            episode_ids[split].append(str(rows[0]["episode_id"]))
    if not grouped["train"] or joint_names is None:
        raise ValueError("no admitted training episodes")
    if set(episode_ids["train"]) & set(episode_ids["validation"]):
        raise ValueError("an episode cannot appear in both train and validation")
    train_x, train_y, joint_count = make_windows(grouped["train"], history_length, context_size)
    if not train_x:
        raise ValueError("no complete training windows after projection")
    model = train_ridge(train_x, train_y, joint_count=joint_count, history_length=history_length, context_size=context_size, ridge=ridge)
    val_x, val_y, _ = make_windows(grouped["validation"], history_length, context_size) if grouped["validation"] else ([], [], joint_count)
    output_dir.mkdir(parents=True)
    model_path = output_dir / "causal_filter_model.json"
    model.save(model_path)
    report = {
        "schema": "robot_teleop.filter-flywheel-round-report/v1", "round_id": round_id,
        "parent_round_id": config.get("parent_round_id"), "condition_id": config.get("condition_id"),
        "created_at": datetime.now(timezone.utc).isoformat(), "code_revision": git_revision(),
        "round_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "model": {"path": str(model_path.resolve()), "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(), "history_length": history_length, "context_size": context_size, "ridge": ridge, "joint_names": joint_names},
        "episodes": episode_ids, "rejected_episodes": rejected,
        "metrics": {"train": prediction_metrics(model, train_x, train_y), "validation": prediction_metrics(model, val_x, val_y)},
        "safety": {"deployment": "simulation_only", "real_hardware_authorized": False, "fallback": "mapped_command_on_invalid_or_ood_input"},
    }
    (output_dir / "round_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = train_round(args.round_config.resolve(), args.output_dir.resolve())
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({"round_id": report["round_id"], "model": report["model"]["path"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
