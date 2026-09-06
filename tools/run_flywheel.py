#!/usr/bin/env python3
"""Run one capture through export, VLM preparation, training and evaluation."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from robot_teleop.flywheel import FlywheelConfig, load_flywheel_config, resolve_capture  # noqa: E402


def run(command: list[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def capture_contract(run_dir: Path, config: FlywheelConfig) -> tuple[str, list[tuple[str, str]], dict[str, str]]:
    manifest_path = run_dir / "artifacts" / "teleop_capture_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    experiment = manifest.get("experiment") or {}
    task_id = str(experiment.get("task_id") or "unclassified_task")
    namespaces = list(manifest.get("camera_namespaces") or [])
    ids = list(config.processing.get("camera_ids") or [])
    if not namespaces:
        namespaces = ["/camera/camera", "/camera2/camera"][:len(ids)]
    if not ids:
        ids = [f"camera_{index + 1}" for index in range(len(namespaces))]
    if len(ids) != len(namespaces):
        raise ValueError("camera_ids count differs from capture camera_namespaces")
    task = {
        "task_id": task_id,
        "task_family": str(experiment.get("task_family") or task_id),
        "success_spec": str(experiment.get("success_spec_version") or task_id),
    }
    return str(config.processing["arm"]), list(zip(ids, namespaces)), task


def stage_paths(run_dir: Path, derived_name: str) -> dict[str, Path]:
    root = run_dir / "derived" / derived_name
    return {
        "root": root,
        "export": root / "export" / "episode.jsonl",
        "quality": root / "reports" / "data_quality.json",
        "frames": root / "frames",
        "canonical": root / "canonical",
        "filter": root / "filter" / "filter_training.jsonl",
        "correction": root / "filter" / "correction_view.jsonl",
        "vlm_dir": root / "filter" / "vlm",
        "view": root / "filter" / "vlm" / "filter_training_vlm.jsonl",
        "state": root / "pipeline_state.json",
    }


def write_state(path: Path, status: str, **values: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": "robot_teleop.flywheel-state/v1", "status": status, **values}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def select_events(run_dir: Path, prefer_reviewed: bool) -> Path | None:
    artifacts = run_dir / "artifacts"
    candidates = [artifacts / "audit_events_reviewed.jsonl", artifacts / "audit_events.jsonl"]
    if not prefer_reviewed:
        candidates.reverse()
    return next((path for path in candidates if path.is_file()), None)


def prepare_episode(source: Path, config: FlywheelConfig, ros_command: list[str], train_python: Path) -> Path:
    run_dir, bag = resolve_capture(source)
    arm, cameras, task = capture_contract(run_dir, config)
    paths = stage_paths(run_dir, str(config.processing["derived_name"]))
    if paths["view"].is_file():
        print(f"[REUSE] {paths['view']}", flush=True)
        return paths["view"]
    paths["root"].mkdir(parents=True, exist_ok=True)
    events = select_events(run_dir, bool(config.processing.get("use_reviewed_events", True)))
    audit = run_dir / "artifacts" / "terminal_audit.json"
    if not audit.is_file():
        write_state(paths["state"], "needs_review", reason="terminal_audit_missing")
        raise ValueError(f"terminal audit missing: {audit}")
    if events is None:
        write_state(paths["state"], "needs_review", reason="human_events_missing")
        raise ValueError(f"human audit events missing under {run_dir / 'artifacts'}")

    camera_args: list[str] = []
    for camera_id, namespace in cameras:
        camera_args += ["--extra-camera-namespace" if camera_args else "--camera-namespace", namespace]
        camera_args += ["--camera-id", camera_id]
    paths["export"].parent.mkdir(parents=True, exist_ok=True)
    if not paths["export"].is_file():
        run([*ros_command, str(ROOT / "tools/export_rosbag_episode.py"),
             "--bag", str(bag), "--output", str(paths["export"]), "--arm", arm,
             "--source-domain", str(config.processing["source_domain"]), *camera_args])
    quality_passed = False
    if paths["quality"].is_file():
        report = read_json(paths["quality"])
        quality_passed = report.get("quality_gate") == "pass"
    if not quality_passed:
        paths["quality"].parent.mkdir(parents=True, exist_ok=True)
        status = subprocess.run([*ros_command, str(ROOT / "tools/score_episode_data_quality.py"),
                                 "--episode", str(paths["export"]), "--config", str(config.quality_gate),
                                 "--output", str(paths["quality"])]).returncode
        if status and config.processing.get("require_quality_pass", True):
            write_state(paths["state"], "needs_review", reason="data_quality_gate", report=str(paths["quality"]))
            raise ValueError(f"data quality gate requires review: {paths['quality']}")
    paths["frames"].mkdir(parents=True, exist_ok=True)
    for camera_id, namespace in cameras:
        index = paths["frames"] / f"{camera_id}_frames.jsonl"
        if not index.is_file():
            run([*ros_command, str(ROOT / "tools/extract_rosbag_images.py"), "--bag", str(bag),
                 "--topic", f"{namespace.rstrip('/')}/color/image_raw", "--output-dir", str(paths["frames"]),
                 "--camera-id", camera_id])
    canonical_manifest = paths["canonical"] / "episode.manifest.json"
    if not canonical_manifest.is_file():
        run([*ros_command, str(ROOT / "tools/exported_jsonl_to_canonical_episode.py"),
             "--export-jsonl", str(paths["export"]), "--output-dir", str(paths["canonical"]),
             "--source", "real" if config.processing["source_domain"] == "real" else "simulation",
             "--task-id", task["task_id"], "--task-family", task["task_family"],
             "--success-spec-version", task["success_spec"], "--collection-mode",
             str(config.processing.get("collection_mode", "teleop_rule")), "--terminal-audit", str(audit),
             "--events-jsonl", str(events)])
    if not paths["filter"].is_file():
        run([*ros_command, str(ROOT / "tools/canonical_episode_to_filter_jsonl.py"),
             "--manifest", str(canonical_manifest), "--output", str(paths["filter"])])
    if not paths["correction"].is_file():
        run([*ros_command, str(ROOT / "tools/build_correction_segment_view.py"),
             "--episode", str(paths["filter"]), "--events", str(events),
             "--expert-action-field", str(config.processing["expert_action_field"]),
             "--output", str(paths["correction"])])
    if config.vlm.get("enabled", True) and not paths["view"].is_file():
        command = ["bash", str(ROOT / "scripts/prepare_vlm_filter_view.sh"),
                   "--episode", str(paths["correction"]), "--output-dir", str(paths["vlm_dir"]),
                   "--model-id", str(config.vlm["model_id"]), "--revision", str(config.vlm["revision"]),
                   "--cache-dir", str(config.model_cache), "--device", str(config.vlm.get("device", "cuda")),
                   "--batch-size", str(config.vlm.get("batch_size", 32)), "--max-age-ms",
                   str(config.processing.get("max_camera_age_ms", 100.0))]
        if config.vlm.get("allow_network", False):
            command.append("--allow-network")
        if config.vlm.get("drop_unmatched", True):
            command.append("--drop-unmatched")
        for camera_id, _ in cameras:
            command += ["--camera", f"{camera_id}={paths['frames'] / f'{camera_id}_frames.jsonl'}"]
        run(command)
    view = paths["view"] if config.vlm.get("enabled", True) else paths["correction"]
    write_state(paths["state"], "prepared", training_view=str(view), task=task, cameras=[item[0] for item in cameras])
    return view


def compatible_views(config: FlywheelConfig, current: Path) -> list[Path]:
    if config.vlm.get("enabled", True):
        pattern = f"evidence/teleop/*/derived/{config.processing['derived_name']}/filter/vlm/filter_training_vlm.jsonl"
    else:
        pattern = f"evidence/teleop/*/derived/{config.processing['derived_name']}/filter/correction_view.jsonl"
    views = sorted(config.data_root.glob(pattern))
    if current not in views:
        views.append(current)
    return sorted(set(path.resolve() for path in views if path.is_file()))


def train_views(views: list[Path], config: FlywheelConfig, train_python: Path) -> Path | None:
    if not config.training.get("enabled", True):
        return None
    validation_count = min(int(config.training.get("validation_episodes", 1)), max(0, len(views) - 1))
    train = views[:-validation_count] if validation_count else views
    validation = views[-validation_count:] if validation_count else []
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = config.run_root / f"flywheel_{timestamp}"
    round_config = config.run_root / "configs" / f"flywheel_{timestamp}.yaml"
    round_config.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "robot_teleop.filter-round-config/v0.1",
        "dataset": {"train": [str(path) for path in train], "validation": [str(path) for path in validation]},
        "training": {
            "model_config": str(config.effective_model_config),
            "device": config.training.get("device", "cuda"),
            "require_cuda": bool(config.training.get("require_cuda", True)),
            "epochs": int(config.training.get("epochs", 50)),
            "batch_size": int(config.training.get("batch_size", 128)),
            "validation_fraction": 0,
        },
        "output": {"directory": str(output), "on_exists": "error"},
        "evaluation": {"device": config.training.get("device", "cuda")},
    }
    round_config.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    run([str(train_python), str(ROOT / "tools/run_filter_round.py"), "--config", str(round_config)])
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="capture run directory or its artifacts/rosbag2 directory")
    parser.add_argument("--config", type=Path, default=ROOT / "config/flywheel/default.yaml")
    parser.add_argument("--prepare-only", action="store_true", help="prepare and validate the training view without starting training")
    args = parser.parse_args()
    config = load_flywheel_config(args.config, ROOT)
    ros_command = [str(ROOT / "skills/ros2-python-env/scripts/run_ros2_python.sh"), "/usr/bin/python3"]
    train_python = Path(sys.executable)
    try:
        view = prepare_episode(args.source, config, ros_command, train_python)
        if args.prepare_only:
            print(json.dumps({"training_view": str(view), "prepared_only": True}, indent=2))
            return 0
        views = compatible_views(config, view)
        output = train_views(views, config, train_python)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        return 2
    print(json.dumps({"training_view": str(view), "dataset_episodes": len(views),
                      "training_run": None if output is None else str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
