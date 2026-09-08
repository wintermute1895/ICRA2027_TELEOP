"""Conditional trajectory VAE with a causal-history Transformer encoder."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import torch
from torch import Tensor, nn
from torch.nn import functional as F


def unroll_rate_limited_gain(
    desired_gain: Tensor,
    episode_start: Tensor,
    *,
    alpha_rate: float,
    initial_alpha: Tensor | None = None,
) -> Tensor:
    """Chronologically unroll scalar gain, resetting at episode boundaries."""
    if desired_gain.ndim != 2 or desired_gain.shape[1] != 1:
        raise ValueError("desired_gain must have shape [time, 1]")
    starts = episode_start.reshape(-1).to(dtype=torch.bool, device=desired_gain.device)
    if starts.shape[0] != desired_gain.shape[0]:
        raise ValueError("episode_start must align with desired_gain")
    previous = (
        desired_gain.new_zeros((1,))
        if initial_alpha is None
        else initial_alpha.to(desired_gain).reshape(1)
    )
    values = []
    for index in range(desired_gain.shape[0]):
        if starts[index]:
            previous = desired_gain.new_zeros((1,))
        target = desired_gain[index]
        previous = previous + (target - previous).clamp(-alpha_rate, alpha_rate)
        values.append(previous)
    return torch.stack(values)


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
    gate_enabled: bool = False
    gain_enabled: bool = False
    alpha_max: float = 1.0
    alpha_rate: float = 0.1
    gain_current_command: bool = False
    shared_action_gain_head: bool = False
    fixed_gain: float | None = None

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
        if self.alpha_max < 0.0 or self.alpha_rate < 0.0:
            raise ValueError("alpha_max and alpha_rate must be non-negative")
        if self.fixed_gain is not None and not 0.0 <= self.fixed_gain <= self.alpha_max:
            raise ValueError("fixed_gain must be within [0, alpha_max]")
        if self.shared_action_gain_head and not self.gain_enabled:
            raise ValueError("shared_action_gain_head requires gain_enabled")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConditionalTrajectoryVAE(nn.Module):
    """Predict expert action targets without consuming future observations at inference."""

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
        self.gate_head = nn.Linear(config.model_dim, 1) if config.gate_enabled else None
        gain_dim = config.model_dim + (config.action_dim if config.gain_current_command else 0)
        self.gain_head = nn.Linear(gain_dim, 1) if config.gain_enabled and not config.shared_action_gain_head else None
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
            nn.Linear(2 * config.model_dim, config.horizon * config.action_dim + int(config.shared_action_gain_head)),
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
        # Enforce strict left-to-right temporal attention.  Without this mask
        # the Transformer encoder is bidirectional inside the history window,
        # which is inconsistent with online filtering and leaks later history
        # positions into earlier representations during training.
        causal_mask = torch.triu(
            torch.ones(cfg.history_length, cfg.history_length, device=tokens.device, dtype=torch.bool),
            diagonal=1,
        )
        encoded = self.history_encoder(tokens, mask=causal_mask)
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
        target_actions: Tensor,
        context: Tensor | None = None,
        visual: Tensor | None = None,
        current_command: Tensor | None = None,
        previous_alpha: Tensor | None = None,
    ) -> dict[str, Tensor]:
        cfg = self.config
        if tuple(target_actions.shape) != (commands.shape[0], cfg.horizon, cfg.action_dim):
            raise ValueError("target_actions does not match configured horizon/action dimensions")
        history = self.encode_history(commands, states, context, visual)
        prior_mean, prior_log_variance = self._distribution(self.prior(history))
        posterior_input = torch.cat([history, target_actions.flatten(start_dim=1)], dim=-1)
        posterior_mean, posterior_log_variance = self._distribution(self.posterior(posterior_input))
        latent = self._sample(posterior_mean, posterior_log_variance)
        decoded = self.decoder(torch.cat([history, latent], dim=-1))
        prediction = decoded[:, :cfg.horizon * cfg.action_dim].view(-1, cfg.horizon, cfg.action_dim)
        shared_gain_logit = decoded[:, -1:] if cfg.shared_action_gain_head else None
        desired_gain, alpha, gain_delta = self._gain_outputs(
            history, current_command, previous_alpha, shared_gain_logit,
        )
        return {
            "prediction": prediction,
            "prior_mean": prior_mean,
            "prior_log_variance": prior_log_variance,
            "posterior_mean": posterior_mean,
            "posterior_log_variance": posterior_log_variance,
            "gate_logits": self.gate_head(history).view(-1, 1) if self.gate_head is not None else None,
            "desired_gain": desired_gain,
            "alpha": alpha,
            "gain_delta": gain_delta,
        }

    def _gain_outputs(
        self, history: Tensor, current_command: Tensor | None, previous_alpha: Tensor | None,
        shared_gain_logit: Tensor | None = None,
    ) -> tuple[Tensor | None, Tensor | None, Tensor | None]:
        if self.config.fixed_gain is not None:
            desired = history.new_full((history.shape[0], 1), self.config.fixed_gain)
            alpha = self._rate_limited_gain(desired, previous_alpha)
            previous = self._previous_gain(alpha, previous_alpha)
            return desired, alpha, alpha - previous
        if self.config.shared_action_gain_head:
            if shared_gain_logit is None:
                raise ValueError("shared gain logit is required")
            desired = torch.sigmoid(shared_gain_logit) * self.config.alpha_max
            alpha = self._rate_limited_gain(desired, previous_alpha)
            previous = self._previous_gain(alpha, previous_alpha)
            return desired, alpha, alpha - previous
        if self.gain_head is None:
            return None, None, None
        if not self.config.gain_current_command:
            gain_delta = torch.tanh(self.gain_head(history)) * self.config.alpha_rate
            previous = self._previous_gain(gain_delta, previous_alpha)
            alpha = (previous + gain_delta).clamp(0.0, self.config.alpha_max)
            return None, alpha, alpha - previous
        if current_command is None or tuple(current_command.shape) != (history.shape[0], self.config.action_dim):
            raise ValueError("current_command is required and must match the action dimension when gain is enabled")
        desired = torch.sigmoid(self.gain_head(torch.cat([history, current_command], dim=-1))) * self.config.alpha_max
        alpha = self._rate_limited_gain(desired, previous_alpha)
        previous = self._previous_gain(alpha, previous_alpha)
        return desired, alpha, alpha - previous

    @staticmethod
    def _previous_gain(reference: Tensor, previous_alpha: Tensor | None) -> Tensor:
        if previous_alpha is None:
            return torch.zeros_like(reference)
        previous = previous_alpha.to(reference)
        if previous.numel() == 1:
            return previous.reshape(1, 1).expand_as(reference)
        if tuple(previous.shape) != tuple(reference.shape):
            raise ValueError("previous_alpha must be scalar or align with the batch")
        return previous

    def _rate_limited_gain(self, desired_gain: Tensor | None, previous_alpha: Tensor | None) -> Tensor | None:
        if desired_gain is None:
            return None
        previous = self._previous_gain(desired_gain, previous_alpha)
        return previous + (desired_gain - previous).clamp(-self.config.alpha_rate, self.config.alpha_rate)

    @torch.no_grad()
    def predict(
        self,
        commands: Tensor,
        states: Tensor,
        context: Tensor | None = None,
        visual: Tensor | None = None,
        previous_alpha: Tensor | None = None,
        current_command: Tensor | None = None,
        *,
        deterministic: bool = True,
    ) -> dict[str, Tensor]:
        history = self.encode_history(commands, states, context, visual)
        prior_mean, prior_log_variance = self._distribution(self.prior(history))
        latent = prior_mean if deterministic else self._sample(prior_mean, prior_log_variance)
        decoded = self.decoder(torch.cat([history, latent], dim=-1))
        action_width = self.config.horizon * self.config.action_dim
        prediction = decoded[:, :action_width].view(-1, self.config.horizon, self.config.action_dim)
        shared_gain_logit = decoded[:, -1:] if self.config.shared_action_gain_head else None
        gate_logits = self.gate_head(history).view(-1, 1) if self.gate_head is not None else None
        desired_gain, alpha, gain_delta = self._gain_outputs(
            history, current_command, previous_alpha, shared_gain_logit,
        )
        return {
            "prediction": prediction,
            "prior_mean": prior_mean,
            "prior_log_variance": prior_log_variance,
            "latent_variance": torch.exp(prior_log_variance).mean(dim=-1),
            "gate_logits": gate_logits,
            "correction_probability": torch.sigmoid(gate_logits) if gate_logits is not None else None,
            "gain_delta": gain_delta,
            "desired_gain": desired_gain,
            "alpha": alpha,
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
    target_actions: Tensor,
    *,
    beta_kl: float = 1e-3,
    smoothness_weight: float = 1e-2,
    reconstruction_weights: Tensor | None = None,
    correction_mask: Tensor | None = None,
    gate_weight: float = 0.0,
    gain_weight: float = 0.0,
    alpha_max: float = 1.0,
    alpha_rate: float = 0.1,
    alpha_low: float = 0.05,
    alpha_high: float = 0.5,
    zero_weight: float = 0.0,
    raw_commands: Tensor | None = None,
    target_mean: Tensor | None = None,
    target_std: Tensor | None = None,
) -> dict[str, Tensor]:
    if beta_kl < 0.0 or smoothness_weight < 0.0 or gate_weight < 0.0 or gain_weight < 0.0 or zero_weight < 0.0:
        raise ValueError("loss weights must be non-negative")
    if not 0.0 <= alpha_low < alpha_high <= alpha_max:
        raise ValueError("gain bands must satisfy 0 <= alpha_low < alpha_high <= alpha_max")
    prediction = outputs["prediction"]
    if target_mean is not None and target_std is not None:
        prediction_for_action = prediction * target_std + target_mean
        target_for_action = target_actions * target_std + target_mean
    else:
        prediction_for_action = prediction
        target_for_action = target_actions
    if reconstruction_weights is None:
        reconstruction = F.smooth_l1_loss(prediction_for_action, target_for_action)
    else:
        if reconstruction_weights.shape != target_actions.shape[:-1] + (1,):
            raise ValueError("reconstruction_weights must align with target batch/horizon")
        if not torch.isfinite(reconstruction_weights).all() or torch.any(reconstruction_weights < 0.0):
            raise ValueError("reconstruction_weights must be finite and non-negative")
        element_loss = F.smooth_l1_loss(prediction_for_action, target_for_action, reduction="none")
        weights = reconstruction_weights.to(dtype=element_loss.dtype)
        reconstruction = (element_loss * weights).sum() / weights.expand_as(element_loss).sum().clamp_min(1e-6)
    kl = diagonal_gaussian_kl(
        outputs["posterior_mean"], outputs["posterior_log_variance"],
        outputs["prior_mean"], outputs["prior_log_variance"],
    ).mean()
    smoothness = prediction_for_action.diff(dim=1).square().mean() if prediction.shape[1] > 1 else prediction.new_zeros(())
    gate = prediction.new_zeros(())
    if gate_weight and outputs.get("gate_logits") is not None:
        if correction_mask is None:
            raise ValueError("correction_mask is required when gate_weight is non-zero")
        labels = correction_mask.to(dtype=prediction.dtype)
        logits = outputs["gate_logits"]
        if logits.shape != labels.shape:
            logits = logits.expand_as(labels)
        gate = F.binary_cross_entropy_with_logits(logits, labels)
    gain = prediction.new_zeros(())
    if gain_weight and outputs.get("alpha") is not None:
        if correction_mask is None:
            raise ValueError("correction_mask is required when gain_weight is non-zero")
        labels = correction_mask.to(dtype=prediction.dtype)
        if labels.ndim > 1:
            labels = labels[:, :1]
        alpha = outputs["alpha"]
        gain = (labels * F.relu(alpha_high - alpha) + (1.0 - labels) * F.relu(alpha - alpha_low)).mean()
    zero = prediction.new_zeros(())
    if zero_weight:
        if correction_mask is None or raw_commands is None or target_mean is None or target_std is None:
            raise ValueError("raw_commands, target statistics and correction_mask are required for zero-residual loss")
        predicted_physical = prediction_for_action
        residual = predicted_physical - raw_commands.to(dtype=prediction.dtype)
        nominal = (1.0 - correction_mask.to(dtype=prediction.dtype)).unsqueeze(-1)
        zero = (residual.abs() * nominal).sum() / nominal.expand_as(residual).sum().clamp_min(1e-6)
    total = reconstruction + beta_kl * kl + smoothness_weight * smoothness + gate_weight * gate + gain_weight * gain + zero_weight * zero
    return {"total": total, "reconstruction": reconstruction, "kl": kl, "smoothness": smoothness, "gate": gate, "gain": gain, "zero_residual": zero}


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
