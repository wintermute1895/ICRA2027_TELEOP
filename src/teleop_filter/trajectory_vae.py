"""Conditional trajectory VAE with a causal-history Transformer encoder."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import torch
from torch import Tensor, nn
from torch.nn import functional as F


@dataclass(frozen=True)
class TrajectoryFilterConfig:
    action_dim: int
    state_dim: int
    history_length: int = 16
    horizon: int = 8
    context_dim: int = 0
    visual_dim: int = 0
    latent_dim: int = 8
    model_dim: int = 128
    num_heads: int = 4
    num_layers: int = 3
    dropout: float = 0.1

    def validate(self) -> None:
        integer_fields = (
            self.action_dim, self.state_dim, self.history_length, self.horizon,
            self.latent_dim, self.model_dim, self.num_heads, self.num_layers,
        )
        if any(value < 1 for value in integer_fields) or self.context_dim < 0 or self.visual_dim < 0:
            raise ValueError("model dimensions must be positive; context_dim and visual_dim may be zero")
        if self.model_dim % self.num_heads:
            raise ValueError("model_dim must be divisible by num_heads")
        if not 0.0 <= self.dropout < 1.0:
            raise ValueError("dropout must be in [0, 1)")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConditionalTrajectoryVAE(nn.Module):
    """Predict residual targets without consuming future observations at inference."""

    def __init__(self, config: TrajectoryFilterConfig) -> None:
        super().__init__()
        config.validate()
        self.config = config
        token_dim = config.action_dim + config.state_dim + config.context_dim + config.visual_dim
        self.input_projection = nn.Linear(token_dim, config.model_dim)
        self.position = nn.Parameter(torch.zeros(1, config.history_length, config.model_dim))
        layer = nn.TransformerEncoderLayer(
            d_model=config.model_dim,
            nhead=config.num_heads,
            dim_feedforward=4 * config.model_dim,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.history_encoder = nn.TransformerEncoder(layer, num_layers=config.num_layers)
        self.history_norm = nn.LayerNorm(config.model_dim)
        self.prior = nn.Linear(config.model_dim, 2 * config.latent_dim)
        self.posterior = nn.Sequential(
            nn.Linear(config.model_dim + config.horizon * config.action_dim, 2 * config.model_dim),
            nn.GELU(),
            nn.Linear(2 * config.model_dim, 2 * config.latent_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(config.model_dim + config.latent_dim, 2 * config.model_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(2 * config.model_dim, config.horizon * config.action_dim),
        )
        nn.init.normal_(self.position, std=0.02)

    def encode_history(
        self,
        commands: Tensor,
        states: Tensor,
        context: Tensor | None = None,
        visual: Tensor | None = None,
    ) -> Tensor:
        cfg = self.config
        expected_commands = (commands.shape[0], cfg.history_length, cfg.action_dim)
        expected_states = (states.shape[0], cfg.history_length, cfg.state_dim)
        if tuple(commands.shape) != expected_commands or tuple(states.shape) != expected_states:
            raise ValueError("commands/states do not match configured batch, history, or feature dimensions")
        parts = [commands, states]
        if cfg.context_dim:
            if context is None or tuple(context.shape) != (commands.shape[0], cfg.history_length, cfg.context_dim):
                raise ValueError("context is required and must align with the history")
            parts.append(context)
        if cfg.visual_dim:
            if visual is None or tuple(visual.shape) != (commands.shape[0], cfg.history_length, cfg.visual_dim):
                raise ValueError("visual embeddings are required and must align with the history")
            parts.append(visual)
        tokens = self.input_projection(torch.cat(parts, dim=-1)) + self.position
        encoded = self.history_encoder(tokens)
        return self.history_norm(encoded[:, -1])

    @staticmethod
    def _distribution(parameters: Tensor) -> tuple[Tensor, Tensor]:
        mean, log_variance = parameters.chunk(2, dim=-1)
        return mean, log_variance.clamp(-10.0, 6.0)

    @staticmethod
    def _sample(mean: Tensor, log_variance: Tensor) -> Tensor:
        return mean + torch.randn_like(mean) * torch.exp(0.5 * log_variance)

    def forward(
        self,
        commands: Tensor,
        states: Tensor,
        target_residuals: Tensor,
        context: Tensor | None = None,
        visual: Tensor | None = None,
    ) -> dict[str, Tensor]:
        cfg = self.config
        if tuple(target_residuals.shape) != (commands.shape[0], cfg.horizon, cfg.action_dim):
            raise ValueError("target_residuals does not match configured horizon/action dimensions")
        history = self.encode_history(commands, states, context, visual)
        prior_mean, prior_log_variance = self._distribution(self.prior(history))
        posterior_input = torch.cat([history, target_residuals.flatten(start_dim=1)], dim=-1)
        posterior_mean, posterior_log_variance = self._distribution(self.posterior(posterior_input))
        latent = self._sample(posterior_mean, posterior_log_variance)
        prediction = self.decoder(torch.cat([history, latent], dim=-1)).view(
            -1, cfg.horizon, cfg.action_dim
        )
        return {
            "prediction": prediction,
            "prior_mean": prior_mean,
            "prior_log_variance": prior_log_variance,
            "posterior_mean": posterior_mean,
            "posterior_log_variance": posterior_log_variance,
        }

    @torch.no_grad()
    def predict(
        self,
        commands: Tensor,
        states: Tensor,
        context: Tensor | None = None,
        visual: Tensor | None = None,
        *,
        deterministic: bool = True,
    ) -> dict[str, Tensor]:
        history = self.encode_history(commands, states, context, visual)
        prior_mean, prior_log_variance = self._distribution(self.prior(history))
        latent = prior_mean if deterministic else self._sample(prior_mean, prior_log_variance)
        prediction = self.decoder(torch.cat([history, latent], dim=-1)).view(
            -1, self.config.horizon, self.config.action_dim
        )
        return {
            "prediction": prediction,
            "prior_mean": prior_mean,
            "prior_log_variance": prior_log_variance,
            "latent_variance": torch.exp(prior_log_variance).mean(dim=-1),
        }


def diagonal_gaussian_kl(
    posterior_mean: Tensor,
    posterior_log_variance: Tensor,
    prior_mean: Tensor,
    prior_log_variance: Tensor,
) -> Tensor:
    variance_ratio = torch.exp(posterior_log_variance - prior_log_variance)
    mean_delta = (posterior_mean - prior_mean).square() * torch.exp(-prior_log_variance)
    return 0.5 * (
        prior_log_variance - posterior_log_variance + variance_ratio + mean_delta - 1.0
    ).sum(dim=-1)


def trajectory_vae_loss(
    outputs: dict[str, Tensor],
    target_residuals: Tensor,
    *,
    beta_kl: float = 1e-3,
    smoothness_weight: float = 1e-2,
) -> dict[str, Tensor]:
    if beta_kl < 0.0 or smoothness_weight < 0.0:
        raise ValueError("loss weights must be non-negative")
    prediction = outputs["prediction"]
    reconstruction = F.smooth_l1_loss(prediction, target_residuals)
    kl = diagonal_gaussian_kl(
        outputs["posterior_mean"], outputs["posterior_log_variance"],
        outputs["prior_mean"], outputs["prior_log_variance"],
    ).mean()
    smoothness = prediction.diff(dim=1).square().mean() if prediction.shape[1] > 1 else prediction.new_zeros(())
    total = reconstruction + beta_kl * kl + smoothness_weight * smoothness
    return {"total": total, "reconstruction": reconstruction, "kl": kl, "smoothness": smoothness}


def bounded_residual_command(
    teleop_command: Tensor,
    predicted_residual: Tensor,
    *,
    blend: float,
    max_correction_rad: float,
) -> tuple[Tensor, Tensor]:
    if teleop_command.shape != predicted_residual.shape:
        raise ValueError("teleop command and predicted residual shapes differ")
    if not 0.0 <= blend <= 1.0 or max_correction_rad < 0.0:
        raise ValueError("invalid blend or correction bound")
    correction = predicted_residual.clamp(-max_correction_rad, max_correction_rad)
    return teleop_command + blend * correction, correction
