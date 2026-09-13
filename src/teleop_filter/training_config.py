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
    gain_weight: float = 0.0
    zero_weight: float = 0.0
    alpha_low: float = 0.05
    alpha_high: float = 0.5
    correction_loss_type: str = "unbalanced_hinge"
    focal_gamma: float = 2.0
    ranking_weight: float = 0.0
    ranking_margin: float = 0.1

    def validate(self) -> None:
        if min(self.beta_kl, self.smoothness_weight, self.correction_weight, self.gate_weight, self.gain_weight, self.zero_weight) < 0.0:
            raise ValueError("loss weights must be non-negative")
        if self.correction_loss_type not in {"unbalanced_hinge", "balanced_bce", "focal", "ranking", "bce_ranking"}:
            raise ValueError("unsupported correction_loss_type")
        if self.focal_gamma < 0.0 or self.ranking_weight < 0.0 or self.ranking_margin < 0.0:
            raise ValueError("focal/ranking parameters must be non-negative")


@dataclass(frozen=True)
class DataConfig:
    allow_synthetic_smoke: bool = False
    target_representation: str = "absolute"
    target_field: str = "expert_action_target_rad"


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
                gain_weight=float(loss.get("gain_weight", 0.0)),
                zero_weight=float(loss.get("zero_weight", 0.0)),
                alpha_low=float(loss.get("alpha_low", 0.05)),
                alpha_high=float(loss.get("alpha_high", 0.5)),
                correction_loss_type=str(loss.get("correction_loss_type", "unbalanced_hinge")),
                focal_gamma=float(loss.get("focal_gamma", 2.0)),
                ranking_weight=float(loss.get("ranking_weight", 0.0)),
                ranking_margin=float(loss.get("ranking_margin", 0.1)),
            ),
            data=DataConfig(
                bool((payload.get("data") or {}).get("allow_synthetic_smoke", False)),
                str((payload.get("data") or {}).get("target_representation", "absolute")),
                str((payload.get("data") or {}).get("target_field", "expert_action_target_rad")),
            ),
            runtime=dict(runtime),
            semantics=dict(payload.get("semantics") or {}),
        )
        result.validate()
        return result

    def validate(self) -> None:
        self.loss.validate()
        if self.data.target_representation not in {"absolute", "delta_from_last_executed", "residual_over_constant_velocity"}:
            raise ValueError("unsupported data.target_representation")
        alpha_max = float(self.model.get("alpha_max", 1.0))
        if not 0.0 <= self.loss.alpha_low < self.loss.alpha_high <= alpha_max:
            raise ValueError("loss gain bands must satisfy 0 <= alpha_low < alpha_high <= alpha_max")
        if int(self.model["horizon"]) < 1:
            raise ValueError("model.horizon must be positive")
        if self.runtime.get("deployment") != "offline_and_simulation_only":
            raise ValueError("training config is not authorized for offline/simulation runtime")
        if self.data.target_field not in {"expert_action_target_rad", "joint_reference_action_rad"}:
            raise ValueError("data.target_field must be expert_action_target_rad or joint_reference_action_rad")
        if self.data.target_field not in str(self.semantics.get("target", "")):
            raise ValueError(f"semantics.target must declare {self.data.target_field}")

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

    def model_config(self, *, action_dim: int, state_dim: int, command_dim: int | None = None) -> TrajectoryFilterConfig:
        return TrajectoryFilterConfig(
            action_dim=action_dim,
            state_dim=state_dim,
            command_dim=command_dim,
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
            gain_enabled=bool(self.model.get("gain_enabled", False)),
            alpha_max=float(self.model.get("alpha_max", 1.0)),
            alpha_rate=float(self.model.get("alpha_rate", 0.1)),
            gain_current_command=bool(self.model.get("gain_current_command", False)),
            shared_action_gain_head=bool(self.model.get("shared_action_gain_head", False)),
            fixed_gain=(None if self.model.get("fixed_gain") is None else float(self.model["fixed_gain"])),
            model_type=str(self.model.get("model_type", "cvae_rate_limited")),
            authority_mode=str(self.model.get("authority_mode", "rate_limited")),
            risk_use_discrepancy=bool(self.model.get("risk_use_discrepancy", True)),
            risk_use_dispersion=bool(self.model.get("risk_use_dispersion", True)),
            risk_use_correction_probability=bool(self.model.get("risk_use_correction_probability", True)),
            zero_initialize_action_head=bool(self.model.get("zero_initialize_action_head", False)),
        )
