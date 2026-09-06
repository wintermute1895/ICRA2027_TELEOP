#!/usr/bin/env python3
"""LeRobot ACT worker. It has no ROS dependency and only returns candidates."""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml

from model_artifacts import sha256_path


class Worker:
    def __init__(self, config: dict) -> None:
        from lerobot.policies.act.modeling_act import ACTPolicy
        from lerobot.policies.act.processor_act import make_act_pre_post_processors

        checkpoint = Path(config["checkpoint"]).expanduser().resolve()
        expected = str(config.get("checkpoint_sha256") or "")
        if not expected or sha256_path(checkpoint) != expected:
            raise ValueError("ACT checkpoint_sha256 does not match checkpoint")
        device = str(config.get("device", "cuda"))
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("ACT requested cuda but CUDA is unavailable")
        self.policy = ACTPolicy.from_pretrained(checkpoint, local_files_only=True)
        # The checkpoint may have been saved with a CPU config.  The runtime
        # device is authoritative for both the model and its processor steps.
        self.policy.config.device = device
        self.policy = self.policy.to(device).eval()
        stats = None
        if config.get("dataset_stats"):
            stats_path = Path(config["dataset_stats"])
            stats = json.loads(stats_path.read_text()) if stats_path.suffix == ".json" else torch.load(stats_path, map_location="cpu", weights_only=False)
        self.preprocessor, self.postprocessor = make_act_pre_post_processors(self.policy.config, stats)
        self.camera_keys = list((config.get("camera_keys") or {}).keys())
        self.state_key = str(config.get("state_key", "observation.state"))

    @staticmethod
    def image(data: bytes) -> torch.Tensor:
        array = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if array is None:
            raise ValueError("cannot decode camera JPEG")
        array = cv2.cvtColor(array, cv2.COLOR_BGR2RGB)
        return torch.from_numpy(np.ascontiguousarray(array)).permute(2, 0, 1)

    def handle(self, request: dict) -> dict:
        batch = {self.state_key: torch.as_tensor(request["state"], dtype=torch.float32)}
        images = request.get("camera_jpeg_base64") or {}
        for key in self.camera_keys:
            batch[key] = self.image(base64.b64decode(images[key]))
        batch = self.preprocessor(batch)
        with torch.inference_mode():
            action = self.policy.select_action(batch)
            action = self.postprocessor.process_action(action)
            action = action.detach().cpu().reshape(-1).numpy().astype(np.float32)
        if action.size == 0 or not np.isfinite(action).all():
            raise ValueError("ACT produced invalid action")
        return {"ready": True, "timestamp_ns": int(request["timestamp_ns"]), "command_rad": action.tolist()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    if config.get("enabled") is not True:
        raise SystemExit("ACT runtime is disabled")
    worker = Worker(config)
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
