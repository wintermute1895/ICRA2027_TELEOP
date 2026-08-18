#!/usr/bin/env python3
"""Convert a DexMimicGen/Robomimic HDF5 subset to a local LeRobot dataset.

This is intentionally a first-phase conversion tool:
- single camera (frontview)
- observation.state from robot0_joint_pos
- action from the raw 24-dimensional HDF5 `actions` field
- synthetic timestamps at `frame_index / fps`
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import numpy as np
from lerobot.datasets.lerobot_dataset import LeRobotDataset


DEFAULT_FEATURES = {
    "timestamp": {"dtype": "float32", "shape": (1,), "names": None},
    "frame_index": {"dtype": "int64", "shape": (1,), "names": None},
    "episode_index": {"dtype": "int64", "shape": (1,), "names": None},
    "index": {"dtype": "int64", "shape": (1,), "names": None},
    "task_index": {"dtype": "int64", "shape": (1,), "names": None},
}


def build_features(state_dim: int, action_dim: int, image_shape: tuple[int, int, int]) -> dict:
    features = dict(DEFAULT_FEATURES)
    features["observation.state"] = {
        "dtype": "float32",
        "shape": (state_dim,),
        "names": None,
    }
    features["action"] = {
        "dtype": "float32",
        "shape": (action_dim,),
        "names": None,
    }
    features["observation.images.frontview"] = {
        "dtype": "video",
        "shape": image_shape,
        "names": ["height", "width", "channels"],
    }
    return features


def sorted_demo_keys(h5_data: h5py.Group) -> list[str]:
    return sorted(h5_data.keys(), key=lambda key: int(key.split("_")[1]))


def convert(
    hdf5_path: str | Path,
    output_root: str | Path,
    repo_id: str,
    fps: int,
    num_episodes: int,
    task: str,
) -> Path:
    hdf5_path = Path(hdf5_path)
    output_root = Path(output_root)

    with h5py.File(hdf5_path, "r") as f:
        data = f["data"]
        keys = sorted_demo_keys(data)
        selected = keys[:num_episodes]
        if not selected:
            raise ValueError("No episodes selected")

        demo0 = data[selected[0]]
        action_dim = int(demo0["actions"].shape[1])
        state_dim = int(demo0["obs"]["robot0_joint_pos"].shape[1])
        image_shape = tuple(int(x) for x in demo0["obs"]["frontview_image"].shape[1:])

        dataset = LeRobotDataset.create(
            repo_id=repo_id,
            fps=fps,
            root=output_root,
            robot_type="robomimic",
            features=build_features(state_dim, action_dim, image_shape),
            use_videos=True,
            image_writer_threads=2,
        )

        for episode_index, key in enumerate(selected):
            demo = data[key]
            num_frames = int(demo.attrs["num_samples"])
            images = demo["obs"]["frontview_image"][:]
            states = demo["obs"]["robot0_joint_pos"][:]
            actions = demo["actions"][:]

            assert images.shape == (num_frames, *image_shape), (images.shape, num_frames, image_shape)
            assert states.shape == (num_frames, state_dim), (states.shape, state_dim)
            assert actions.shape == (num_frames, action_dim), (actions.shape, action_dim)

            for frame_index in range(num_frames):
                dataset.add_frame(
                    {
                        "observation.state": states[frame_index].astype(np.float32),
                        "action": actions[frame_index].astype(np.float32),
                        "observation.images.frontview": images[frame_index],
                    },
                    task=task,
                    timestamp=frame_index / float(fps),
                )

            dataset.save_episode()
            print(
                f"converted episode {key} -> LeRobot episode {episode_index}, "
                f"frames={num_frames}"
            )

    summary_path = output_root / "conversion_summary.json"
    summary = {
        "source_hdf5": str(hdf5_path),
        "output_root": str(output_root),
        "repo_id": repo_id,
        "fps": fps,
        "num_episodes": len(selected),
        "action_dim": action_dim,
        "state_dim": state_dim,
        "image_shape": list(image_shape),
        "selected_episodes": selected,
        "task": task,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {summary_path}")
    return output_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hdf5", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--repo-id", default="dexmimicgen_two_arm_can_sort_subset")
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--num-episodes", type=int, default=3)
    parser.add_argument("--task", default="TwoArmCanSort")
    args = parser.parse_args()

    convert(
        hdf5_path=args.hdf5,
        output_root=args.output_root,
        repo_id=args.repo_id,
        fps=args.fps,
        num_episodes=args.num_episodes,
        task=args.task,
    )


if __name__ == "__main__":
    main()
