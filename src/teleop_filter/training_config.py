"""Validated, typed configuration for trajectory-filter training."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .trajectory_vae import TrajectoryFilterConfig


MODEL_CONFIG_SCHEMA = "robot_teleop.trajectory-filter-model/v0.1"


@dataclass(frozen=True)
class LossConfig:
    beta_kl: float
    smoothness_weight: float
    correction_weight: float
    gate_weight: float = 0.0
    zero_weight: float = 0.0

    def validate(self) -> None:
        if min(self.beta_kl, self.smoothness_weight, self.correction_weight, self.gate_weight, self.zero_weight) < 0.0:
            raise ValueError("loss weights must be non-negative")


@dataclass(frozen=True)
class DataConfig:
    allow_synthetic_smoke: bool = False


@dataclass(frozen=True)
class FilterTrainingConfig:
    model: Mapping[str, Any]
    loss: LossConfig
    data: DataConfig
    runtime: Mapping[str, Any]
    semantics: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "FilterTrainingConfig":
        if payload.get("schema") != MODEL_CONFIG_SCHEMA:
            raise ValueError(f"unsupported model config schema: {payload.get('schema')}")
        model = payload.get("model")
        loss = payload.get("loss")
        runtime = payload.get("runtime")
        if not all(isinstance(item, Mapping) for item in (model, loss, runtime)):
            raise ValueError("model, loss and runtime must be mappings")
        required_model = {
            "history_length", "horizon", "latent_dim", "model_dim", "num_heads",
            "num_layers", "dropout", "context_dim", "visual_dim",
        }
        missing = sorted(required_model - set(model))
        if missing:
            raise ValueError(f"model config lacks fields: {', '.join(missing)}")
        result = cls(
            model=dict(model),
            loss=LossConfig(
                beta_kl=float(loss.get("beta_kl", 1e-3)),
                smoothness_weight=float(loss.get("smoothness_weight", 1e-2)),
                correction_weight=float(loss.get("correction_weight", 1.0)),
                gate_weight=float(loss.get("gate_weight", 0.0)),
                zero_weight=float(loss.get("zero_weight", 0.0)),
            ),
            data=DataConfig(bool((payload.get("data") or {}).get("allow_synthetic_smoke", False))),
            runtime=dict(runtime),
            semantics=dict(payload.get("semantics") or {}),
        )
        result.validate()
        return result

    def validate(self) -> None:
        self.loss.validate()
        if int(self.model["horizon"]) != 1:
            raise ValueError("the task-aware action-filter MVP requires horizon=1")
        if self.runtime.get("deployment") != "offline_and_simulation_only":
            raise ValueError("training config is not authorized for offline/simulation runtime")
        if "expert_action_target_rad" not in str(self.semantics.get("target", "")):
            raise ValueError("semantics.target must declare expert_action_target_rad")

    @property
    def history_length(self) -> int:
        return int(self.model["history_length"])

    @property
    def horizon(self) -> int:
        return int(self.model["horizon"])

    @property
    def context_dim(self) -> int:
        return int(self.model["context_dim"])

    @property
    def visual_dim(self) -> int:
        return int(self.model["visual_dim"])

    def model_config(self, *, action_dim: int, state_dim: int) -> TrajectoryFilterConfig:
        return TrajectoryFilterConfig(
            action_dim=action_dim,
            state_dim=state_dim,
            history_length=self.history_length,
            horizon=self.horizon,
            context_dim=self.context_dim,
            visual_dim=self.visual_dim,
            latent_dim=int(self.model["latent_dim"]),
            model_dim=int(self.model["model_dim"]),
            num_heads=int(self.model["num_heads"]),
            num_layers=int(self.model["num_layers"]),
            dropout=float(self.model["dropout"]),
            gate_enabled=bool(self.model.get("gate_enabled", False)),
        )
