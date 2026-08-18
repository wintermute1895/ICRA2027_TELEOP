"""Dependency-light causal action-prior filter used by simulation experiments.

The model is deliberately conservative.  It predicts an action from only the
current/past mapped commands and robot states, then blends that prediction
with the mapped command.  Invalid inputs, missing state, or out-of-distribution
features always fall back to the mapped command.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Sequence

import numpy as np


@dataclass
class CausalFilterModel:
    schema: str
    joint_count: int
    history_length: int
    feature_mean: list[float]
    feature_scale: list[float]
    weights: list[list[float]]
    bias: list[float]
    residual_scale: list[float]
    training_samples: int

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "CausalFilterModel":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != "robot_teleop.causal-command-filter/v0":
            raise ValueError("unsupported causal filter model schema")
        model = cls(**payload)
        feature_size = model.joint_count * (model.history_length + 1)
        if len(model.feature_mean) != feature_size or len(model.feature_scale) != feature_size:
            raise ValueError("model feature dimensions are inconsistent")
        if len(model.weights) != model.joint_count or any(len(row) != feature_size for row in model.weights):
            raise ValueError("model weight dimensions are inconsistent")
        return model


def _finite_vector(values: Sequence[float], length: int) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.shape != (length,) or not np.isfinite(result).all():
        raise ValueError(f"expected {length} finite values")
    return result


def build_feature(history: Sequence[Sequence[float]], state: Sequence[float], joint_count: int, history_length: int) -> np.ndarray:
    if len(history) != history_length:
        raise ValueError(f"expected {history_length} command-history frames")
    commands = [_finite_vector(frame, joint_count) for frame in history]
    return np.concatenate([*commands, _finite_vector(state, joint_count)])


def train_ridge(features: Sequence[np.ndarray], targets: Sequence[Sequence[float]], *, joint_count: int, history_length: int, ridge: float = 1e-3) -> CausalFilterModel:
    if not features or len(features) != len(targets):
        raise ValueError("features and targets must be non-empty and aligned")
    if ridge < 0.0:
        raise ValueError("ridge must be non-negative")
    x = np.vstack(features)
    y = np.vstack([_finite_vector(target, joint_count) for target in targets])
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-6] = 1.0
    normalized = (x - mean) / scale
    augmented = np.column_stack([normalized, np.ones(len(normalized))])
    regularizer = np.eye(augmented.shape[1]) * ridge
    regularizer[-1, -1] = 0.0
    coefficients = np.linalg.solve(augmented.T @ augmented + regularizer, augmented.T @ y)
    predictions = augmented @ coefficients
    residual_scale = np.maximum(np.std(y - predictions, axis=0), 1e-5)
    return CausalFilterModel(
        schema="robot_teleop.causal-command-filter/v0",
        joint_count=joint_count,
        history_length=history_length,
        feature_mean=mean.tolist(),
        feature_scale=scale.tolist(),
        weights=coefficients[:-1].T.tolist(),
        bias=coefficients[-1].tolist(),
        residual_scale=residual_scale.tolist(),
        training_samples=len(features),
    )


def predict(model: CausalFilterModel, history: Sequence[Sequence[float]], state: Sequence[float]) -> tuple[np.ndarray, float]:
    feature = build_feature(history, state, model.joint_count, model.history_length)
    mean = np.asarray(model.feature_mean, dtype=np.float64)
    scale = np.asarray(model.feature_scale, dtype=np.float64)
    normalized = (feature - mean) / scale
    prediction = np.asarray(model.weights, dtype=np.float64) @ normalized + np.asarray(model.bias, dtype=np.float64)
    # RMS feature z-score is an OOD diagnostic, not a task-success estimate.
    return prediction, float(math.sqrt(float(np.mean(normalized * normalized))))


def blend_command(
    model: CausalFilterModel,
    history: Sequence[Sequence[float]],
    state: Sequence[float],
    *,
    blend: float,
    max_correction_rad: float,
    max_ood_z: float,
) -> tuple[list[float], dict[str, float | bool]]:
    baseline = _finite_vector(history[-1], model.joint_count)
    if not 0.0 <= blend <= 1.0 or max_correction_rad < 0.0 or max_ood_z <= 0.0:
        raise ValueError("invalid blend or safety bound")
    prediction, ood_z = predict(model, history, state)
    confidence = max(0.0, min(1.0, 1.0 - ood_z / max_ood_z))
    alpha = blend * confidence
    correction = np.clip(prediction - baseline, -max_correction_rad, max_correction_rad)
    output = baseline + alpha * correction
    if not np.isfinite(output).all():
        return baseline.tolist(), {"fallback": True, "ood_z": ood_z, "confidence": 0.0, "blend": 0.0}
    return output.tolist(), {"fallback": alpha == 0.0, "ood_z": ood_z, "confidence": confidence, "blend": alpha}
