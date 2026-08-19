#!/usr/bin/env python3
"""Rollout a trained LeRobot ACT policy inside DexMimicGen/Robosuite.

The adapter reconstructs the observation.state used during dataset conversion from
`robot0_joint_pos_sin` and `robot0_joint_pos_cos`, then feeds the policy the same
single `frontview` camera it was trained on. The raw 24-dimensional action output
is clipped to the environment action limits and passed directly to `env.step`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import dexmimicgen  # noqa: F401  (registers environments)
import h5py
import numpy as np
import robosuite
import torch
from lerobot.policies.act.modeling_act import ACTPolicy


def load_env_from_hdf5(hdf5_path: Path):
    with h5py.File(hdf5_path, "r") as f:
        env_args = json.loads(f["data"].attrs["env_args"])
    env_kwargs = env_args["env_kwargs"]

    return robosuite.make(
        env_name=env_args["env_name"],
        robots=env_kwargs["robots"],
        controller_configs=env_kwargs["controller_configs"],
        env_configuration=env_kwargs.get("env_configuration", "single-robot"),
        reward_shaping=env_kwargs.get("reward_shaping", False),
        camera_names=["frontview"],
        camera_heights=84,
        camera_widths=84,
        has_renderer=False,
        has_offscreen_renderer=True,
        ignore_done=True,
        use_object_obs=env_kwargs.get("use_object_obs", True),
        use_camera_obs=True,
        camera_depths=False,
        render_gpu_device_id=0,
        control_freq=20,
        horizon=1000,
        renderer="mujoco",
        render_camera="frontview",
    )


def state_from_obs(obs: dict) -> np.ndarray:
    sin = obs["robot0_joint_pos_sin"].astype(np.float32)
    cos = obs["robot0_joint_pos_cos"].astype(np.float32)
    return np.arctan2(sin, cos).astype(np.float32)


def image_from_obs(obs: dict) -> torch.Tensor:
    frame = obs["frontview_image"].astype(np.float32) / 255.0
    frame = np.ascontiguousarray(frame.transpose(2, 0, 1))
    return torch.from_numpy(frame).unsqueeze(0)


def rollout(
    hdf5_path: Path,
    policy_path: Path,
    output_dir: Path,
    max_steps: int,
    seed: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    video_path = output_dir / "rollout.mp4"
    log_path = output_dir / "rollout_log.jsonl"

    policy = ACTPolicy.from_pretrained(policy_path, local_files_only=True)
    policy_device = torch.device(policy.config.device)
    env = load_env_from_hdf5(hdf5_path)

    np.random.seed(seed)
    torch.manual_seed(seed)
    env.reset()
    policy.reset()

    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        20.0,
        (84, 84),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer for {video_path}")

    records = []
    obs = env.reset()
    low, high = env.action_spec

    for step in range(max_steps):
        state = state_from_obs(obs)
        image = image_from_obs(obs)

        with torch.no_grad():
            action_tensor = policy.select_action(
                {
                    "observation.state": torch.from_numpy(state).unsqueeze(0).to(policy_device),
                    "observation.images.frontview": image.to(policy_device),
                }
            )
        action = action_tensor.squeeze(0).cpu().numpy().astype(np.float64)
        action = np.clip(action, low, high)

        obs, reward, done, info = env.step(action)
        frame = obs["frontview_image"].copy()
        # MuJoCo/robosuite default observation images are bottom-up. Flip
        # vertically before encoding so the deployment video looks correct.
        frame = cv2.flip(frame, 0)
        writer.write(frame)

        record = {
            "step": step,
            "timestamp_s": step / 20.0,
            "action": [float(x) for x in action],
            "observation_state": [float(x) for x in state],
            "reward": float(reward),
            "done": bool(done),
        }
        records.append(record)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    writer.release()
    summary = {
        "hdf5_path": str(hdf5_path),
        "policy_path": str(policy_path),
        "output_dir": str(output_dir),
        "max_steps": max_steps,
        "actual_steps": len(records),
        "video_path": str(video_path),
        "log_path": str(log_path),
        "action_dim": len(records[0]["action"]) if records else None,
        "state_dim": len(records[0]["observation_state"]) if records else None,
    }
    summary_path = output_dir / "rollout_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hdf5", required=True, type=Path)
    parser.add_argument(
        "--policy",
        required=True,
        type=Path,
        help="Path to LeRobot pretrained_model directory",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-steps", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    rollout(args.hdf5, args.policy, args.output_dir, args.max_steps, args.seed)


if __name__ == "__main__":
    main()
