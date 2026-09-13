#!/usr/bin/env python3
"""Standalone arm7 IMLE worker. It has no ROS dependency and only returns candidates."""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import yaml

from model_artifacts import sha256_path
from imle_arm7_contract import (
    ACTION_HORIZON,
    CANDIDATE_COUNT,
    OBS_HORIZON,
    PRED_HORIZON,
    executed_chunk,
    resolve_imle_root,
    select_candidate_index,
    should_reset_action_chunk,
    validate_action,
    validate_image_chw,
    validate_payload_config,
    validate_runtime_config,
    validate_state,
)


Normalization = dict[str, Any]


def _stat_block(normalization: Normalization, *names: str) -> dict[str, Any]:
    for name in names:
        block = normalization.get(name)
        if isinstance(block, dict):
            return block
    raise ValueError(f"IMLE normalization is missing {'/'.join(names)}")


def _vector_stat(block: dict[str, Any], key: str) -> torch.Tensor:
    if key not in block:
        raise ValueError(f"IMLE normalization is missing {key}")
    return torch.as_tensor(block[key], dtype=torch.float32)


def load_imle_policy(checkpoint: Path, imle_root: Path, device: torch.device):
    src = imle_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        from robot_policy_imle.checkpoint import load_model_state, validate_payload
        from robot_policy_imle.model import IMLEPolicy
    except ImportError as error:
        raise RuntimeError(
            f"cannot import robot_policy_imle from {imle_root}; "
            "set imle_root or IMLE_ROOT to the ICRA2027_TELEOP_IMLE checkout"
        ) from error

    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    runtime = validate_payload(payload)
    validate_payload_config(runtime)
    model = IMLEPolicy(runtime)
    state = None
    for key in ("ema_state", "model_state", "state_dict", "model"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if value is not None:
            state = value
            break
    if state is None:
        raise ValueError("IMLE deployment payload has no model weights")
    dimensions = getattr(runtime, "generator_dimensions", None)
    try:
        load_model_state(model, state, dimensions)
    except TypeError:
        load_model_state(model, state)
    except Exception:
        model.load_state_dict(state)
    model.to(device).eval()
    normalization = payload.get("normalization") or payload.get("stats")
    if not isinstance(normalization, dict):
        raise ValueError("IMLE deployment payload is missing normalization statistics")
    return model, runtime, normalization


class Worker:
    def __init__(self, config: dict) -> None:
        validate_runtime_config(config)
        checkpoint = Path(config["checkpoint"]).expanduser().resolve()
        expected = str(config.get("checkpoint_sha256") or "")
        if not expected or sha256_path(checkpoint) != expected:
            raise ValueError("IMLE checkpoint_sha256 does not match checkpoint")
        device = str(config.get("device", "cuda"))
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("IMLE requested cuda but CUDA is unavailable")
        self.device = torch.device(device)
        imle_root = resolve_imle_root(config)
        self.model, runtime, normalization = load_imle_policy(checkpoint, imle_root, self.device)
        self.pred_horizon = int(getattr(runtime, "pred_horizon", PRED_HORIZON))
        self.action_horizon = int(getattr(runtime, "action_horizon", ACTION_HORIZON))
        self.obs_horizon = int(getattr(runtime, "obs_horizon", OBS_HORIZON))
        self.candidate_count = int(
            getattr(runtime, "candidate_count", getattr(runtime, "n_samples_per_condition", CANDIDATE_COUNT))
        )
        state_stats = _stat_block(normalization, "state", "observation.state")
        action_stats = _stat_block(normalization, "action")
        self.state_mean = _vector_stat(state_stats, "mean").to(self.device)
        self.state_std = _vector_stat(state_stats, "std").clamp_min(1e-6).to(self.device)
        self.action_mean = _vector_stat(action_stats, "mean").to(self.device)
        self.action_std = _vector_stat(action_stats, "std").clamp_min(1e-6).to(self.device)
        self.camera_keys = list((config.get("camera_keys") or {}).keys())
        self.inference_hz = float(config.get("inference_hz", 50.0))
        self._last_timestamp_ns: int | None = None
        self._states: deque[np.ndarray] = deque(maxlen=self.obs_horizon)
        self._images: dict[str, deque[torch.Tensor]] = {
            key: deque(maxlen=self.obs_horizon) for key in self.camera_keys
        }
        self._queue: deque[np.ndarray] = deque()
        self._prev_traj: np.ndarray | None = None
        self._rng = np.random.default_rng(int(config.get("seed", 42)))

    def reset_action_chunk(self) -> None:
        self._last_timestamp_ns = None
        self._states.clear()
        for window in self._images.values():
            window.clear()
        self._queue.clear()
        self._prev_traj = None

    @staticmethod
    def image(data: bytes) -> torch.Tensor:
        array = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if array is None:
            raise ValueError("cannot decode camera JPEG")
        array = cv2.cvtColor(array, cv2.COLOR_BGR2RGB)
        if array.shape[0] != 480 or array.shape[1] != 640:
            interpolation = (
                cv2.INTER_AREA
                if array.shape[0] > 480 or array.shape[1] > 640
                else cv2.INTER_LINEAR
            )
            array = cv2.resize(array, (640, 480), interpolation=interpolation)
        image = np.ascontiguousarray(array).transpose(2, 0, 1)
        validate_image_chw(image)
        return torch.from_numpy(image).float() / 255.0

    def _windowed_state(self) -> torch.Tensor:
        frames = list(self._states)
        while len(frames) < self.obs_horizon:
            frames.insert(0, frames[0])
        stacked = np.stack(frames[-self.obs_horizon :], axis=0)
        tensor = torch.from_numpy(stacked).to(self.device)
        return ((tensor - self.state_mean) / self.state_std).unsqueeze(0)

    def _windowed_images(self) -> dict[str, torch.Tensor]:
        images: dict[str, torch.Tensor] = {}
        for key, window in self._images.items():
            frames = list(window)
            while len(frames) < self.obs_horizon:
                frames.insert(0, frames[0])
            images[key] = torch.stack(frames[-self.obs_horizon :], dim=0).unsqueeze(0).to(self.device)
        return images

    def _plan(self) -> None:
        noise = torch.randn(
            1,
            self.candidate_count,
            self.pred_horizon,
            7,
            device=self.device,
        )
        with torch.inference_mode():
            candidates = self.model.candidates(self._windowed_state(), self._windowed_images(), noise)
        predicted = candidates.detach().float().cpu().numpy()
        if predicted.ndim == 4:
            predicted = predicted[0]
        index = select_candidate_index(
            predicted,
            self._prev_traj,
            action_horizon=self.action_horizon,
            rng=self._rng,
        )
        selected = predicted[index]
        self._prev_traj = selected.copy()
        denorm = selected * self.action_std.detach().cpu().numpy() + self.action_mean.detach().cpu().numpy()
        for action in executed_chunk(denorm, self.action_horizon):
            self._queue.append(validate_action(action))

    def handle(self, request: dict) -> dict:
        timestamp_ns = int(request["timestamp_ns"])
        if should_reset_action_chunk(
            last_timestamp_ns=self._last_timestamp_ns,
            timestamp_ns=timestamp_ns,
            inference_hz=self.inference_hz,
            requested=bool(request.get("reset")),
        ):
            self.reset_action_chunk()
        self._last_timestamp_ns = timestamp_ns
        state = validate_state(request.get("state"))
        self._states.append(state)
        images = request.get("camera_jpeg_base64") or {}
        for key in self.camera_keys:
            if key not in images:
                raise ValueError(f"missing camera input: {key}")
            self._images[key].append(self.image(base64.b64decode(images[key])).cpu())
        if not self._queue:
            self._plan()
        action = validate_action(self._queue.popleft())
        return {
            "ready": True,
            "timestamp_ns": timestamp_ns,
            "command_rad": action.tolist(),
            "queued": len(self._queue),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    if config.get("enabled") is not True:
        raise SystemExit("IMLE runtime is disabled")
    started = time.monotonic()
    socket_path = Path(config["socket"])
    socket_path.unlink(missing_ok=True)
    worker = Worker(config)
    print(f"[IMLE] model loaded in {time.monotonic() - started:.1f}s; inference ready", flush=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    os.chmod(socket_path, 0o600)
    server.listen(1)
    print(f"[READY] IMLE worker: {socket_path}", flush=True)
    try:
        while True:
            connection, _ = server.accept()
            with connection, connection.makefile("rwb") as stream:
                for line in stream:
                    try:
                        result = worker.handle(json.loads(line))
                    except Exception as error:
                        worker.reset_action_chunk()
                        result = {"ready": False, "reason": f"inference_error:{type(error).__name__}"}
                    stream.write((json.dumps(result) + "\n").encode())
                    stream.flush()
    finally:
        server.close()
        socket_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
