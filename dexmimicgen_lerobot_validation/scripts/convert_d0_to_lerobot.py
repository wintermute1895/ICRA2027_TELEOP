#!/usr/bin/env python3
"""Convert extracted D0 NumPy episodes to the existing LeRobot ACT format."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from lerobot.datasets.lerobot_dataset import LeRobotDataset


def features(state_dim: int, action_dim: int) -> dict:
    return {
        "timestamp": {"dtype": "float32", "shape": (1,), "names": None},
        "frame_index": {"dtype": "int64", "shape": (1,), "names": None},
        "episode_index": {"dtype": "int64", "shape": (1,), "names": None},
        "index": {"dtype": "int64", "shape": (1,), "names": None},
        "task_index": {"dtype": "int64", "shape": (1,), "names": None},
        "observation.state": {"dtype": "float32", "shape": (state_dim,), "names": None},
        "action": {"dtype": "float32", "shape": (action_dim,), "names": None},
        "observation.images.frontview": {
            "dtype": "video",
            "shape": (84, 84, 3),
            "names": ["height", "width", "channels"],
        },
    }


def convert(input_dir: Path, output_root: Path, repo_id: str, fps: int, task: str) -> None:
    files = sorted(input_dir.glob("d0_right_hand_*.npz"))
    if not files:
        raise RuntimeError(f"no extracted episodes found in {input_dir}")
    first = np.load(files[0])
    state_dim = int(first["states"].shape[1])
    action_dim = int(first["actions"].shape[1])
    if state_dim != 13 or action_dim != 13:
        raise ValueError(f"expected 13-dimensional arm+O6 data, got {state_dim}/{action_dim}")

    dataset = LeRobotDataset.create(
        repo_id=repo_id,
        fps=fps,
        root=output_root,
        robot_type="d0_right_arm_o6",
        features=features(state_dim, action_dim),
        use_videos=True,
        image_writer_threads=2,
        video_backend="pyav",
    )
    episode_summaries = []
    for episode_index, path in enumerate(files):
        data = np.load(path)
        images = data["images"]
        states = data["states"]
        actions = data["actions"]
        timestamps = data["timestamps"]
        if not (len(images) == len(states) == len(actions) == len(timestamps)):
            raise ValueError(f"length mismatch in {path}")
        for frame_index in range(len(images)):
            dataset.add_frame(
                {
                    "observation.state": states[frame_index].astype(np.float32),
                    "action": actions[frame_index].astype(np.float32),
                    "observation.images.frontview": images[frame_index],
                },
                task=task,
                timestamp=float(timestamps[frame_index]),
            )
        dataset.save_episode()
        episode_summaries.append({"source": str(path), "frames": int(len(images))})
        print(f"converted {path.name}: frames={len(images)}")

    summary = {
        "repo_id": repo_id,
        "output_root": str(output_root),
        "fps": fps,
        "state_dim": state_dim,
        "action_dim": action_dim,
        "episodes": episode_summaries,
        "task": task,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "d0_conversion_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--repo-id", default="d0_right_arm_o6_005_008")
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--task", default="right_arm_teleop_with_o6")
    args = parser.parse_args()
    convert(args.input_dir, args.output_root, args.repo_id, args.fps, args.task)


if __name__ == "__main__":
    main()
