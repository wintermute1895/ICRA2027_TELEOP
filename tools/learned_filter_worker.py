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
import time
from collections import deque
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from teleop_filter import SafetyLimits, SafetyProjector, TrajectoryFilterRuntime  # noqa: E402
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
        if self.runtime.command_semantics not in {"master_joint_raw", "raw_and_executed_action_history"}:
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
        safety = config.get("safety")
        if not isinstance(safety, dict):
            raise ValueError("learned-filter runtime requires an explicit safety mapping")
        self.safety = SafetyProjector(SafetyLimits(
            joint_min_rad=np.asarray(safety["joint_min_rad"], dtype=np.float32),
            joint_max_rad=np.asarray(safety["joint_max_rad"], dtype=np.float32),
            max_residual_rad=float(safety["max_residual_rad"]),
            max_residual_rate_rad_s=float(safety["max_residual_rate_rad_s"]),
            max_command_velocity_rad_s=float(safety["max_command_velocity_rad_s"]),
            max_model_age_ms=float(safety["max_model_age_ms"]),
        ))
        self.inference_hz = float(config.get("inference_hz", 5.0))
        self.execution_mode = str(config.get("execution_mode", "receding_horizon"))
        if self.execution_mode not in {"receding_horizon", "open_loop_chunk"}:
            raise ValueError("execution_mode must be receding_horizon or open_loop_chunk")
        self.open_loop_actions: deque[np.ndarray] = deque()
        self.last_latent_variance = 0.0
        self.last_desired_gain: float | None = None
        self.alpha = 0.0
        self.previous_timestamp_ns: int | None = None

    def reset_episode(self) -> None:
        self.commands.clear()
        self.states.clear()
        self.visuals.clear()
        self.open_loop_actions.clear()
        self.alpha = 0.0
        self.previous_timestamp_ns = None
        self.safety.reset()

    def handle(self, request: dict) -> dict:
        if request.get("reset_episode") is True:
            self.reset_episode()
            return {"ready": False, "reason": "episode_reset"}
        baseline = np.asarray(request["master_joint_raw_rad"], dtype=np.float32)
        state = np.asarray(request["robot_joint_state_rad"], dtype=np.float32)
        encoded = request.get("camera_jpeg_base64") or {}
        visual = self.encoder.encode_jpegs([base64.b64decode(encoded[name]) for name in self.camera_ids])
        self.states.append(state)
        self.visuals.append(visual)
        if len(self.commands) < self.runtime.config.history_length:
            projected = self.safety.project(
                baseline, np.zeros_like(baseline), dt_s=1.0 / self.inference_hz,
                model_age_ms=self._model_age_ms(request), measured_state_rad=state,
            )
            history_action = np.concatenate([baseline, projected.command_rad])
            self.commands.append(history_action if self.runtime.config.effective_command_dim == 2 * baseline.size else baseline)
            return {"ready": False, "reason": "history_warmup",
                    "command_rad": projected.command_rad.tolist(),
                    "residual_rad": projected.applied_residual_rad.tolist(),
                    "alpha": 0.0, "safety_reasons": list(projected.reasons)}
        prediction = None
        if self.execution_mode == "open_loop_chunk" and self.open_loop_actions:
            predicted_action = self.open_loop_actions.popleft()
            gate = 1.0
        else:
            prediction = self.runtime.predict(
                np.stack(self.commands)[None, ...], np.stack(self.states)[None, ...],
                visuals=np.stack(self.visuals)[None, ...], previous_alpha=self.alpha,
                current_command=baseline[None, :],
            )
            gate = 1.0
            if prediction.correction_probability is not None:
                gate = float(prediction.correction_probability[0, 0])
            if prediction.alpha is not None:
                self.alpha = float(prediction.alpha[0, 0])
            predicted_action = prediction.predicted_actions[0, 0]
            self.last_latent_variance = float(prediction.latent_variance[0])
            self.last_desired_gain = None if prediction.desired_gain is None else float(prediction.desired_gain[0, 0])
            if self.execution_mode == "open_loop_chunk":
                self.open_loop_actions.extend(prediction.predicted_actions[0, 1:])
        authority = self.alpha if self.runtime.config.gain_enabled else gate
        proposed_residual = (predicted_action - baseline) * authority
        timestamp_ns = int(request["timestamp_ns"])
        dt_s = (
            1.0 / self.inference_hz
            if self.previous_timestamp_ns is None
            else max((timestamp_ns - self.previous_timestamp_ns) / 1_000_000_000.0, 1e-6)
        )
        projected = self.safety.project(
            baseline, proposed_residual, dt_s=dt_s, model_age_ms=self._model_age_ms(request),
            measured_state_rad=state,
        )
        self.previous_timestamp_ns = timestamp_ns
        history_action = np.concatenate([baseline, projected.command_rad])
        self.commands.append(history_action if self.runtime.config.effective_command_dim == 2 * baseline.size else baseline)
        return {
            "ready": True,
            "timestamp_ns": int(request["timestamp_ns"]),
            "command_rad": projected.command_rad.tolist(),
            "residual_rad": projected.applied_residual_rad.tolist(),
            "latent_variance": self.last_latent_variance,
            "correction_probability": gate,
            "alpha": self.alpha,
            "desired_gain": self.last_desired_gain,
            "gain_delta": None if prediction is None or prediction.gain_delta is None else float(prediction.gain_delta[0, 0]),
            "execution_mode": self.execution_mode,
            "safety_reasons": list(projected.reasons),
        }

    @staticmethod
    def _model_age_ms(request: dict) -> float:
        submitted = request.get("submitted_monotonic_ns")
        if not isinstance(submitted, int):
            return 0.0
        return max((time.monotonic_ns() - submitted) / 1_000_000.0, 0.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    socket_path: Path | None = None
    try:
        config = load_config(args.config)
        # Remove any stale socket from a previous run before the slow model
        # load begins; start_learned_filter.sh only waits for the socket file.
        socket_path = Path(config["socket"])
        if socket_path.exists():
            socket_path.unlink()
        worker = Worker(config)
    except (KeyError, OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    assert socket_path is not None
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
