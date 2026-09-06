"""Checkpoint loading and bounded offline inference for trajectory filters."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor

from .trajectory_vae import (
    ConditionalTrajectoryVAE,
    TrajectoryFilterConfig,
)


@dataclass(frozen=True)
class TrajectoryFilterPrediction:
    predicted_actions: np.ndarray
    predicted_residuals: np.ndarray
    latent_variance: np.ndarray
    correction_probability: np.ndarray | None = None


class TrajectoryFilterRuntime:
    """Inference-only wrapper around a versioned local checkpoint."""

    def __init__(self, checkpoint: dict[str, Any], device: str | torch.device = "cpu") -> None:
        if checkpoint.get("schema") != "robot_teleop.trajectory-filter-checkpoint/v0.1":
            raise ValueError("unsupported trajectory-filter checkpoint schema")
        self.device = torch.device(device)
        self.config = TrajectoryFilterConfig(**checkpoint["model_config"])
        self.model = ConditionalTrajectoryVAE(self.config).to(self.device)
        self.model.load_state_dict(checkpoint["model_state"])
        self.model.eval()
        self.normalization = checkpoint["normalization"]
        self.visual_encoder = checkpoint.get("visual_encoder")
        self.target_semantics = checkpoint.get("target_semantics", "residual")
        self.command_semantics = checkpoint.get("command_semantics", "master_joint_raw")
        if self.target_semantics not in {"residual", "synthetic_smoke_residual", "recorded_expert_action"}:
            raise ValueError(f"unsupported target semantics: {self.target_semantics}")
        if self.config.visual_dim:
            if not isinstance(self.visual_encoder, dict):
                raise ValueError("visual checkpoint lacks frozen-encoder provenance")
            if int(self.visual_encoder.get("embedding_dim", -1)) != self.config.visual_dim:
                raise ValueError("visual checkpoint embedding dimension disagrees with model config")
        self.runtime = dict(checkpoint.get("runtime") or {})
        if self.runtime.get("deployment") not in (None, "offline_and_simulation_only"):
            raise ValueError("checkpoint is not authorized for this offline runtime")

    @classmethod
    def load(cls, path: Path, device: str | torch.device = "cpu") -> "TrajectoryFilterRuntime":
        # Checkpoints are local training artifacts. Explicitly disabling weights-only
        # mode is needed because normalization arrays are stored alongside weights.
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        if not isinstance(checkpoint, dict):
            raise ValueError("trajectory-filter checkpoint must contain a mapping")
        return cls(checkpoint, device=device)

    def _normalized(self, name: str, values: np.ndarray) -> Tensor:
        stats = self.normalization.get(name)
        if not isinstance(stats, dict) or "mean" not in stats or "std" not in stats:
            raise ValueError(f"checkpoint lacks normalization for {name}")
        mean = np.asarray(stats["mean"], dtype=np.float32)
        std = np.asarray(stats["std"], dtype=np.float32)
        if np.any(std <= 0.0):
            raise ValueError(f"checkpoint contains non-positive normalization scale for {name}")
        return torch.from_numpy((np.asarray(values, dtype=np.float32) - mean) / std).to(self.device)

    def predict(
        self,
        commands: np.ndarray,
        states: np.ndarray,
        contexts: np.ndarray | None = None,
        visuals: np.ndarray | None = None,
        *,
        deterministic: bool | None = None,
    ) -> TrajectoryFilterPrediction:
        command_tensor = self._normalized("commands", commands)
        state_tensor = self._normalized("states", states)
        context_tensor = None
        if self.config.context_dim:
            if contexts is None:
                raise ValueError("checkpoint requires context history")
            context_tensor = self._normalized("contexts", contexts)
        visual_tensor = None
        if self.config.visual_dim:
            if visuals is None:
                raise ValueError("checkpoint requires VLM visual embedding history")
            visual_tensor = self._normalized("visuals", visuals)
        deterministic = (
            bool(self.runtime.get("deterministic_prior", True))
            if deterministic is None else deterministic
        )
        with torch.inference_mode():
            outputs = self.model.predict(
                command_tensor, state_tensor, context_tensor, visual_tensor, deterministic=deterministic
            )
            target_stats = self.normalization["targets"]
            target_mean = torch.as_tensor(
                target_stats["mean"], dtype=torch.float32, device=self.device
            )
            target_std = torch.as_tensor(
                target_stats["std"], dtype=torch.float32, device=self.device
            )
            predicted_actions = outputs["prediction"] * target_std + target_mean
            if self.target_semantics == "recorded_expert_action":
                raw_current = torch.as_tensor(commands[:, -1:, :], dtype=torch.float32, device=self.device)
                predicted_residuals = predicted_actions - raw_current
            else:
                predicted_residuals = predicted_actions
        return TrajectoryFilterPrediction(
            predicted_actions=predicted_actions.cpu().numpy(),
            predicted_residuals=predicted_residuals.cpu().numpy(),
            latent_variance=outputs["latent_variance"].cpu().numpy(),
            correction_probability=None if outputs.get("correction_probability") is None else outputs["correction_probability"].cpu().numpy(),
        )
