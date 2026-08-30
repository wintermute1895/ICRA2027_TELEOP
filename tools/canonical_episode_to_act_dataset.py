#!/usr/bin/env python3
"""Project canonical v0.1 episodes into a deterministic ACT/LeRobot-ready view.

The output deliberately remains a projection, never a replacement for the
canonical episode.  It uses portable JSONL and image references so the project
does not silently depend on a particular LeRobot release.  A small versioned
loader can map these fields to the installed LeRobot schema at train time.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


PROJECTION_VERSION = "canonical-to-act/v0.1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_not_after(rows: list[dict[str, Any]], timestamp_ns: int, tolerance_ns: int) -> dict[str, Any] | None:
    selected = None
    for row in rows:
        stamp = int(row["timestamp_ns"])
        if stamp > timestamp_ns:
            break
        if timestamp_ns - stamp <= tolerance_ns:
            selected = row
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--camera-id", default="rgb", help="camera_id value in streams/cameras JSONL")
    parser.add_argument("--image-root", type=Path, help="Root used to resolve relative frame_reference values")
    parser.add_argument("--copy-images", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "teleop_episode/v0.1":
        raise SystemExit("manifest must use teleop_episode/v0.1")
    if "policy_training" not in manifest.get("intended_uses", []):
        raise SystemExit("episode is not admitted for policy_training")
    streams = manifest["streams"]
    control_ref = Path(streams["control"]["storage_ref"])
    camera_stream = streams.get("cameras", {}).get("recorded_frames")
    if not camera_stream or camera_stream.get("availability") != "available":
        raise SystemExit("no available camera frame stream for ACT projection")
    camera_ref = Path(camera_stream["storage_ref"])
    controls = read_jsonl(control_ref)
    cameras = sorted((row for row in read_jsonl(camera_ref) if row.get("camera_id") == args.camera_id), key=lambda row: int(row["timestamp_ns"]))
    if not controls or not cameras:
        raise SystemExit("control or selected camera stream is empty")
    tolerance_ns = int(manifest.get("clock", {}).get("alignment_tolerance_ns", 100_000_000))
    output = args.output_dir
    images = output / "images" / args.camera_id
    images.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for index, control in enumerate(controls):
        timestamp = int(control["timestamp_ns"])
        camera = latest_not_after(cameras, timestamp, tolerance_ns)
        command = control.get("execution", {}).get("controller_command")
        state = control.get("robot", {}).get("q_rad")
        if camera is None or not isinstance(command, list) or not isinstance(state, list):
            excluded.append({"index": index, "timestamp_ns": timestamp, "reason": "missing_aligned_camera_state_or_action"})
            continue
        reference = camera.get("reference", {}).get("frame_reference")
        image_path = None
        if isinstance(reference, str):
            source = Path(reference)
            if not source.is_absolute() and args.image_root:
                source = args.image_root / source
            if source.is_file():
                target = images / f"{timestamp}{source.suffix.lower() or '.png'}"
                if args.copy_images:
                    shutil.copy2(source, target)
                else:
                    target = source
                image_path = str(target)
        if image_path is None:
            excluded.append({"index": index, "timestamp_ns": timestamp, "reason": "camera_reference_is_not_a_decodable_image_file"})
            continue
        rows.append({
            "episode_index": 0, "frame_index": len(rows), "timestamp_ns": timestamp,
            f"observation.images.{args.camera_id}": image_path,
            "observation.state": state, "action": command,
            "next.done": False,
            "metadata": {"episode_id": manifest["episode_id"], "source": manifest["source"], "configuration_id": manifest["configuration"]["configuration_id"], "split": manifest["configuration"]["split"]},
        })
    if not rows:
        raise SystemExit("no ACT rows could be projected; extract ROS image payloads first")
    rows[-1]["next.done"] = True
    data_path = output / "episode_000000.jsonl"
    data_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    (output / "projection_manifest.json").write_text(json.dumps({
        "schema": "robot_teleop.act-projection/v0.1", "projection_version": PROJECTION_VERSION,
        "canonical_manifest": str(args.manifest.resolve()), "camera_id": args.camera_id,
        "resampling": "latest_not_after", "alignment_tolerance_ns": tolerance_ns,
        "normalization": "not_applied; fit training-split statistics in trainer", "included_rows": len(rows), "excluded_rows": excluded,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "rows": len(rows), "excluded": len(excluded)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
