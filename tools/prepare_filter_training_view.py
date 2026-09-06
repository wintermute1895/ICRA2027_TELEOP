#!/usr/bin/env python3
"""Run the correction-segment and optional frozen-VLM pipeline from one YAML file."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from teleop_filter.pipeline_config import FilterViewPipelineConfig, load_pipeline_config  # noqa: E402


def run(config: FilterViewPipelineConfig) -> Path:
    if not config.episode.is_file():
        raise SystemExit(f"episode not found: {config.episode}")
    if config.events is not None and not config.events.is_file():
        raise SystemExit(f"events file not found: {config.events}")
    if config.vlm_enabled:
        for camera in config.cameras:
            if not camera.index.is_file():
                raise SystemExit(f"frame index not found for {camera.camera_id}: {camera.index}")
    if config.output_dir.exists():
        raise SystemExit(f"refusing to overwrite output: {config.output_dir}")
    config.output_dir.mkdir(parents=True)
    try:
        correction = config.output_dir / "correction_view.jsonl"
        command = [sys.executable, str(ROOT / "tools/build_correction_segment_view.py"),
                   "--episode", str(config.episode), "--expert-action-field", config.expert_action_field,
                   "--output", str(correction)]
        if config.events is not None:
            command += ["--events", str(config.events)]
        print("[1/2] correction segment view", flush=True)
        subprocess.run(command, check=True)
        result = correction
        if config.vlm_enabled:
            vlm_dir = config.output_dir / "vlm"
            command = ["bash", str(ROOT / "scripts/prepare_vlm_filter_view.sh"),
                       "--episode", str(correction), "--output-dir", str(vlm_dir),
                       "--model-id", config.model_id, "--revision", config.revision,
                       "--device", config.device, "--batch-size", str(config.batch_size),
                       "--max-age-ms", str(config.max_age_ms)]
            if config.cache_dir is not None:
                command += ["--cache-dir", str(config.cache_dir)]
            if config.allow_network:
                command.append("--allow-network")
            for camera in config.cameras:
                command += ["--camera", f"{camera.camera_id}={camera.index}"]
            print("[2/2] frozen VLM attachment", flush=True)
            subprocess.run(command, check=True)
            result = vlm_dir / "filter_training_vlm.jsonl"
    except Exception:
        # The output path was new and is owned by this run. Remove only this
        # newly-created incomplete bundle so a corrected run can be retried.
        shutil.rmtree(config.output_dir, ignore_errors=True)
        raise
    manifest = {
        "schema": "robot_teleop.filter-training-pipeline-run/v0.1",
        "config": str(config.config_path),
        "config_sha256": hashlib.sha256(config.config_path.read_bytes()).hexdigest(),
        "source_episode": str(config.episode),
        "source_events": None if config.events is None else str(config.events),
        "output": str(result),
        "vlm_enabled": config.vlm_enabled,
        "model_id": config.model_id if config.vlm_enabled else None,
        "model_revision": config.revision if config.vlm_enabled else None,
        "camera_ids": [camera.camera_id for camera in config.cameras],
    }
    (config.output_dir / "pipeline_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"[DONE] {result}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(load_pipeline_config(args.config))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"[FATAL] {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
