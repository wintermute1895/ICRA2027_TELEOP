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
    gain_delta: np.ndarray | None = None
    alpha: np.ndarray | None = None
    desired_gain: np.ndarray | None = None
    uncertainty: np.ndarray | None = None
    uncertainty_type: str | None = None


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
        self.target_field = checkpoint.get("target_field", "expert_action_target_rad")
        self.joint_reference_config_sha256 = checkpoint.get("joint_reference_config_sha256")
        self.target_representation = checkpoint.get("target_representation", "absolute")
        self.command_semantics = checkpoint.get("command_semantics", "master_joint_raw")
        self.model_type = checkpoint.get("model_type", self.config.model_type)
        if self.model_type != self.config.model_type:
            raise ValueError("checkpoint model_type disagrees with model_config")
        if self.target_semantics not in {"residual", "synthetic_smoke_residual", "recorded_expert_action", "delta_from_last_executed", "residual_over_constant_velocity"}:
            raise ValueError(f"unsupported target semantics: {self.target_semantics}")
        if self.target_field not in {"expert_action_target_rad", "joint_reference_action_rad"}:
            raise ValueError(f"unsupported target field: {self.target_field}")
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
        previous_alpha: float | np.ndarray | None = None,
        current_command: np.ndarray | None = None,
        *,
        deterministic: bool | None = None,
    ) -> TrajectoryFilterPrediction:
        command_tensor = self._normalized("commands", commands)
        current_command_physical = (
            np.asarray(commands[:, -1, :self.config.action_dim], dtype=np.float32)
            if current_command is None
            else np.asarray(current_command, dtype=np.float32)
        )
        current_command_tensor = (
            command_tensor[:, -1, :self.config.action_dim]
            if current_command is None
            else self._normalized_current_command(np.asarray(current_command, dtype=np.float32))
        )
        target_stats = self.normalization["targets"]
        discrepancy_physical = current_command_physical
        if self.target_representation in {"delta_from_last_executed", "residual_over_constant_velocity"}:
            discrepancy_physical = discrepancy_physical - self._action_reference(commands)[:, 0]
        discrepancy_command_tensor = torch.as_tensor(
            (discrepancy_physical - np.asarray(target_stats["mean"]).reshape(-1))
            / np.asarray(target_stats["std"]).reshape(-1), dtype=torch.float32, device=self.device,
        )
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
                command_tensor, state_tensor, context_tensor, visual_tensor,
                None if previous_alpha is None else torch.as_tensor(previous_alpha, dtype=torch.float32, device=self.device).reshape(-1, 1),
                current_command=current_command_tensor,
                discrepancy_command=discrepancy_command_tensor,
                deterministic=deterministic
            )
            target_mean = torch.as_tensor(
                target_stats["mean"], dtype=torch.float32, device=self.device
            )
            target_std = torch.as_tensor(
                target_stats["std"], dtype=torch.float32, device=self.device
            )
            predicted_actions = outputs["prediction"] * target_std + target_mean
            if self.target_representation in {"delta_from_last_executed", "residual_over_constant_velocity"}:
                reference = torch.as_tensor(self._action_reference(commands), dtype=torch.float32, device=self.device)
                predicted_actions = predicted_actions + reference
            if self.target_semantics in {"recorded_expert_action", "delta_from_last_executed", "residual_over_constant_velocity"}:
                raw_current = torch.as_tensor(current_command_physical[:, None, :], dtype=torch.float32, device=self.device)
                predicted_residuals = predicted_actions - raw_current
            else:
                predicted_residuals = predicted_actions
        return TrajectoryFilterPrediction(
            predicted_actions=predicted_actions.cpu().numpy(),
            predicted_residuals=predicted_residuals.cpu().numpy(),
            latent_variance=outputs["latent_variance"].cpu().numpy(),
            correction_probability=None if outputs.get("correction_probability") is None else outputs["correction_probability"].cpu().numpy(),
            gain_delta=None if outputs.get("gain_delta") is None else outputs["gain_delta"].cpu().numpy(),
            alpha=None if outputs.get("alpha") is None else outputs["alpha"].cpu().numpy(),
            desired_gain=None if outputs.get("desired_gain") is None else outputs["desired_gain"].cpu().numpy(),
            uncertainty=None if outputs.get("uncertainty") is None else outputs["uncertainty"].cpu().numpy(),
            uncertainty_type=outputs.get("uncertainty_type"),
        )

    def _action_reference(self, commands: np.ndarray) -> np.ndarray:
        executed = np.asarray(commands[..., self.config.action_dim:2 * self.config.action_dim], dtype=np.float32)
        anchor = executed[:, -1]
        if self.target_representation == "residual_over_constant_velocity":
            velocity = anchor - executed[:, -2]
            steps = np.arange(1, self.config.horizon + 1, dtype=np.float32)[None, :, None]
            return anchor[:, None, :] + steps * velocity[:, None, :]
        return np.repeat(anchor[:, None, :], self.config.horizon, axis=1)

    def _normalized_current_command(self, current_command: np.ndarray) -> torch.Tensor:
        stats = self.normalization.get("raw_commands")
        if stats is None:
            command_stats = self.normalization["commands"]
            stats = {
                "mean": np.asarray(command_stats["mean"])[..., :self.config.action_dim],
                "std": np.asarray(command_stats["std"])[..., :self.config.action_dim],
            }
        value = current_command[:, None, :]
        return torch.as_tensor(
            (value - np.asarray(stats["mean"])) / np.asarray(stats["std"]),
            dtype=torch.float32, device=self.device,
        )[:, 0]
