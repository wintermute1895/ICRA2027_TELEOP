#!/usr/bin/env python3
"""LeRobot ACT worker. It has no ROS dependency and only returns candidates."""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml

from model_artifacts import sha256_path
from act_arm7_contract import (
    validate_action,
    validate_image_chw,
    validate_policy_config,
    validate_runtime_config,
    validate_state,
)


class Worker:
    def __init__(self, config: dict) -> None:
        from lerobot.policies.act.modeling_act import ACTPolicy

        validate_runtime_config(config)
        checkpoint = Path(config["checkpoint"]).expanduser().resolve()
        expected = str(config.get("checkpoint_sha256") or "")
        if not expected or sha256_path(checkpoint) != expected:
            raise ValueError("ACT checkpoint_sha256 does not match checkpoint")
        device = str(config.get("device", "cuda"))
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("ACT requested cuda but CUDA is unavailable")
        self.device = torch.device(device)
        stats_path = str(config.get("dataset_stats") or "")
        if not stats_path:
            raise ValueError("ACT arm7 deployment requires dataset_stats from the training dataset")
        stats_file = Path(stats_path).expanduser().resolve()
        if not stats_file.is_file():
            raise FileNotFoundError(f"ACT dataset_stats not found: {stats_file}")
        loaded_stats = json.loads(stats_file.read_text(encoding="utf-8"))
        stats = {
            key: {
                stat: torch.as_tensor(value, dtype=torch.float32)
                for stat, value in values.items()
                if stat in {"min", "max", "mean", "std"}
            }
            for key, values in loaded_stats.items()
        }
        self.policy = ACTPolicy.from_pretrained(checkpoint, dataset_stats=stats, local_files_only=True)
        validate_policy_config(self.policy.config)
        # The checkpoint may have been saved with a CPU config.  The runtime
        # device is authoritative for both the model and its processor steps.
        self.policy.config.device = device
        self.policy = self.policy.to(device).eval()
        self.camera_keys = list((config.get("camera_keys") or {}).keys())
        self.state_key = str(config.get("state_key", "observation.state"))

    @staticmethod
    def image(data: bytes) -> torch.Tensor:
        array = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if array is None:
            raise ValueError("cannot decode camera JPEG")
        array = cv2.cvtColor(array, cv2.COLOR_BGR2RGB)
        image = np.ascontiguousarray(array).transpose(2, 0, 1)
        validate_image_chw(image)
        return torch.from_numpy(image).float() / 255.0

    def handle(self, request: dict) -> dict:
        state = validate_state(request.get("state"))
        batch = {self.state_key: torch.from_numpy(state).unsqueeze(0).to(self.device)}
        images = request.get("camera_jpeg_base64") or {}
        for key in self.camera_keys:
            if key not in images:
                raise ValueError(f"missing camera input: {key}")
            batch[key] = self.image(base64.b64decode(images[key])).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            action = self.policy.select_action(batch)
            action = action.detach().cpu().reshape(-1).numpy().astype(np.float32)
        action = validate_action(action)
        return {"ready": True, "timestamp_ns": int(request["timestamp_ns"]), "command_rad": action.tolist()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    if config.get("enabled") is not True:
        raise SystemExit("ACT runtime is disabled")
    started = time.monotonic()
    worker = Worker(config)
    print(f"[ACT] model loaded in {time.monotonic() - started:.1f}s; inference ready", flush=True)
    socket_path = Path(config["socket"])
    socket_path.unlink(missing_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path)); os.chmod(socket_path, 0o600); server.listen(1)
    print(f"[READY] ACT worker: {socket_path}", flush=True)
    try:
        while True:
            connection, _ = server.accept()
            with connection, connection.makefile("rwb") as stream:
                for line in stream:
                    try:
                        result = worker.handle(json.loads(line))
                    except Exception as error:
                        result = {"ready": False, "reason": f"inference_error:{type(error).__name__}"}
                    stream.write((json.dumps(result) + "\n").encode()); stream.flush()
    finally:
        server.close(); socket_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
