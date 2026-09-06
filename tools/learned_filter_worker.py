#!/usr/bin/env python3
"""GPU model worker for the ROS learned-filter adapter over a Unix socket."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import sys
from collections import deque
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from teleop_filter import TrajectoryFilterRuntime  # noqa: E402
from teleop_filter.online_visual import OnlineVisualEncoder  # noqa: E402


def load_config(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if value.get("schema") != "robot_teleop.learned-filter-runtime/v1":
        raise ValueError("unsupported learned-filter runtime config")
    if value.get("enabled") is not True:
        raise ValueError("learned filter is disabled in runtime config")
    return value


class Worker:
    def __init__(self, config: dict) -> None:
        checkpoint = Path(config["checkpoint"]).expanduser().resolve()
        expected = str(config.get("checkpoint_sha256") or "")
        actual = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if not expected or actual != expected:
            raise ValueError("checkpoint_sha256 must match the promoted checkpoint")
        self.runtime = TrajectoryFilterRuntime.load(checkpoint, device=str(config.get("device", "cuda")))
        if self.runtime.command_semantics != "master_joint_raw":
            raise ValueError(f"checkpoint command space is not deployable: {self.runtime.command_semantics}")
        provenance = self.runtime.visual_encoder or {}
        self.camera_ids = list(provenance.get("camera_ids") or [])
        configured_ids = [item["id"] for item in config.get("cameras", [])]
        if configured_ids != self.camera_ids:
            raise ValueError("runtime camera order differs from checkpoint camera order")
        self.encoder = OnlineVisualEncoder(
            str(provenance["model_id"]), str(provenance["model_revision"]),
            Path(config["model_cache"]), str(config.get("device", "cuda")),
        )
        length = self.runtime.config.history_length
        self.commands: deque[np.ndarray] = deque(maxlen=length)
        self.states: deque[np.ndarray] = deque(maxlen=length)
        self.visuals: deque[np.ndarray] = deque(maxlen=length)
        self.blend = float(config.get("residual_blend", 0.1))
        self.limit = float(config.get("max_residual_rad", 0.01))

    def handle(self, request: dict) -> dict:
        baseline = np.asarray(request["master_joint_raw_rad"], dtype=np.float32)
        state = np.asarray(request["robot_joint_state_rad"], dtype=np.float32)
        encoded = request.get("camera_jpeg_base64") or {}
        visual = self.encoder.encode_jpegs([base64.b64decode(encoded[name]) for name in self.camera_ids])
        self.commands.append(baseline)
        self.states.append(state)
        self.visuals.append(visual)
        if len(self.commands) < self.runtime.config.history_length:
            return {"ready": False, "reason": "history_warmup"}
        prediction = self.runtime.predict(
            np.stack(self.commands)[None, ...], np.stack(self.states)[None, ...],
            visuals=np.stack(self.visuals)[None, ...],
        )
        gate = 1.0
        if prediction.correction_probability is not None:
            gate = float(prediction.correction_probability[0, 0])
        residual = np.clip(prediction.predicted_residuals[0, 0] * self.blend * gate, -self.limit, self.limit)
        return {
            "ready": True,
            "timestamp_ns": int(request["timestamp_ns"]),
            "command_rad": (baseline + residual).tolist(),
            "residual_rad": residual.tolist(),
            "latent_variance": float(prediction.latent_variance[0]),
            "correction_probability": gate,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        worker = Worker(config)
    except (KeyError, OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    socket_path = Path(config["socket"])
    if socket_path.exists():
        socket_path.unlink()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    os.chmod(socket_path, 0o600)
    server.listen(1)
    print(f"[READY] learned-filter worker: {socket_path}", flush=True)
    try:
        while True:
            connection, _ = server.accept()
            with connection, connection.makefile("rwb") as stream:
                for line in stream:
                    try:
                        response = worker.handle(json.loads(line))
                    except Exception as error:
                        response = {"ready": False, "reason": f"inference_error:{type(error).__name__}"}
                    stream.write((json.dumps(response) + "\n").encode())
                    stream.flush()
    finally:
        server.close()
        socket_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
