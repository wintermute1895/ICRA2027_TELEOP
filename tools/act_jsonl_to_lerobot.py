#!/usr/bin/env python3
"""Write an ACT projection JSONL as an official local LeRobot v3 dataset."""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import cv2
import numpy as np
from lerobot.datasets.lerobot_dataset import LeRobotDataset


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def infer_fps(rows: list[dict]) -> int:
    stamps = [int(row["timestamp_ns"]) for row in rows]
    deltas = [right - left for left, right in zip(stamps, stamps[1:]) if right > left]
    if not deltas:
        raise ValueError("at least two increasing timestamps are required to infer fps")
    return max(1, int(round(1_000_000_000 / statistics.median(deltas))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-id", default="local/icra2027-teleop-smoke")
    parser.add_argument("--task", default="precision alignment")
    parser.add_argument("--robot-type", default="linker_a7")
    parser.add_argument("--fps", type=int, help="fixed dataset rate; inferred from timestamps by default")
    args = parser.parse_args()

    rows = read_rows(args.input_jsonl)
    if not rows:
        raise SystemExit("input projection is empty")
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite LeRobot dataset: {args.output_dir}")

    state = rows[0].get("observation.state")
    action = rows[0].get("action")
    if not isinstance(state, list) or not state or not isinstance(action, list) or not action:
        raise SystemExit("first row lacks non-empty observation.state or action")
    if len(state) != len(action):
        raise SystemExit("state/action dimensions differ")
    image_keys = sorted(key for key in rows[0] if key.startswith("observation.images."))
    if not image_keys:
        raise SystemExit("input projection has no observation.images.* field")

    first_images: dict[str, np.ndarray] = {}
    for key in image_keys:
        image = cv2.imread(str(rows[0][key]), cv2.IMREAD_COLOR)
        if image is None:
            raise SystemExit(f"cannot read image for {key}: {rows[0][key]}")
        first_images[key] = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    dimension = len(state)
    joint_names = [f"joint_{index + 1}" for index in range(dimension)]
    features = {
        "observation.state": {"dtype": "float32", "shape": (dimension,), "names": joint_names},
        "action": {"dtype": "float32", "shape": (dimension,), "names": joint_names},
    }
    for key, image in first_images.items():
        features[key] = {
            "dtype": "image",
            "shape": tuple(image.shape),
            "names": ["height", "width", "channels"],
        }

    fps = args.fps or infer_fps(rows)
    if fps < 1:
        raise SystemExit("fps must be positive")
    dataset = LeRobotDataset.create(
        repo_id=args.repo_id,
        fps=fps,
        root=args.output_dir,
        robot_type=args.robot_type,
        features=features,
        use_videos=False,
        image_writer_processes=0,
        image_writer_threads=0,
    )
    for index, row in enumerate(rows):
        frame = {
            "observation.state": np.asarray(row.get("observation.state"), dtype=np.float32),
            "action": np.asarray(row.get("action"), dtype=np.float32),
            "task": args.task,
        }
        for key in image_keys:
            image = first_images[key] if index == 0 else cv2.imread(str(row.get(key)), cv2.IMREAD_COLOR)
            if image is None:
                raise SystemExit(f"cannot read image for {key} at row {index}: {row.get(key)}")
            if index != 0:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            if tuple(image.shape) != tuple(features[key]["shape"]):
                raise SystemExit(f"image shape changed for {key} at row {index}: {image.shape}")
            frame[key] = image
        dataset.add_frame(frame)
    dataset.save_episode(parallel_encoding=False)
    dataset.finalize()

    reopened = LeRobotDataset(args.repo_id, root=args.output_dir)
    if len(reopened) != len(rows) or reopened.meta.total_episodes != 1:
        raise SystemExit("saved LeRobot dataset failed local reopen verification")
    print(json.dumps({
        "output": str(args.output_dir), "repo_id": args.repo_id, "fps": fps,
        "frames": len(reopened), "episodes": reopened.meta.total_episodes,
        "features": sorted(features),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
