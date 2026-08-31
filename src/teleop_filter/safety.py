"""Model-independent safety projection for learned residual commands."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SafetyLimits:
    joint_min_rad: np.ndarray
    joint_max_rad: np.ndarray
    max_residual_rad: float
    max_residual_rate_rad_s: float
    max_command_velocity_rad_s: float
    max_model_age_ms: float

    def validate(self) -> None:
        low = np.asarray(self.joint_min_rad, dtype=np.float32)
        high = np.asarray(self.joint_max_rad, dtype=np.float32)
        if low.ndim != 1 or high.shape != low.shape or np.any(low >= high):
            raise ValueError("joint limits must be aligned one-dimensional low/high vectors")
        scalars = (
            self.max_residual_rad,
            self.max_residual_rate_rad_s,
            self.max_command_velocity_rad_s,
            self.max_model_age_ms,
        )
        if any(not np.isfinite(value) or value < 0.0 for value in scalars):
            raise ValueError("safety limits must be finite and non-negative")


@dataclass(frozen=True)
class ProjectionResult:
    command_rad: np.ndarray
    applied_residual_rad: np.ndarray
    fallback: bool
    reasons: tuple[str, ...]


class SafetyProjector:
    """Stateful final authority after any rule-based or learned filter."""

    def __init__(self, limits: SafetyLimits) -> None:
        limits.validate()
        self.limits = limits
        self._previous_residual: np.ndarray | None = None
        self._previous_command: np.ndarray | None = None

    def reset(self) -> None:
        self._previous_residual = None
        self._previous_command = None

    def project(
        self,
        baseline_command_rad: np.ndarray,
        proposed_residual_rad: np.ndarray,
        *,
        dt_s: float,
        model_age_ms: float,
        enabled: bool = True,
    ) -> ProjectionResult:
        baseline = np.asarray(baseline_command_rad, dtype=np.float32)
        residual = np.asarray(proposed_residual_rad, dtype=np.float32)
        joint_min = np.asarray(self.limits.joint_min_rad, dtype=np.float32)
        joint_max = np.asarray(self.limits.joint_max_rad, dtype=np.float32)
        if baseline.shape != joint_min.shape or residual.shape != baseline.shape:
            raise ValueError("baseline, residual and joint-limit dimensions must match")
        reasons: list[str] = []
        fallback = False
        if not enabled:
            reasons.append("manual_bypass")
            fallback = True
        if not np.isfinite(baseline).all() or not np.isfinite(residual).all():
            reasons.append("non_finite_input")
            fallback = True
        if not np.isfinite(dt_s) or dt_s <= 0.0:
            reasons.append("invalid_dt")
            fallback = True
        if not np.isfinite(model_age_ms) or model_age_ms > self.limits.max_model_age_ms:
            reasons.append("model_timeout")
            fallback = True
        if np.any(baseline < joint_min) or np.any(baseline > joint_max):
            reasons.append("baseline_outside_joint_limits")
            fallback = True
        if fallback:
            safe_baseline = np.clip(np.nan_to_num(baseline), joint_min, joint_max)
            self._previous_residual = np.zeros_like(safe_baseline)
            self._previous_command = safe_baseline
            return ProjectionResult(safe_baseline, np.zeros_like(safe_baseline), True, tuple(reasons))

        bounded = np.clip(
            residual, -self.limits.max_residual_rad, self.limits.max_residual_rad
        )
        if not np.allclose(bounded, residual):
            reasons.append("residual_magnitude_limited")
        if self.limits.max_residual_rate_rad_s > 0.0:
            delta = self.limits.max_residual_rate_rad_s * dt_s
            previous_residual = (
                self._previous_residual
                if self._previous_residual is not None
                else np.zeros_like(bounded)
            )
            rate_limited = np.clip(
                bounded, previous_residual - delta, previous_residual + delta
            )
            if not np.allclose(rate_limited, bounded):
                reasons.append("residual_rate_limited")
            bounded = rate_limited
        command = np.clip(baseline + bounded, joint_min, joint_max)
        if not np.allclose(command, baseline + bounded):
            reasons.append("joint_position_limited")
        if self.limits.max_command_velocity_rad_s > 0.0:
            delta = self.limits.max_command_velocity_rad_s * dt_s
            previous_command = (
                self._previous_command
                if self._previous_command is not None
                else baseline
            )
            velocity_limited = np.clip(
                command, previous_command - delta, previous_command + delta
            )
            if not np.allclose(velocity_limited, command):
                reasons.append("command_velocity_limited")
            command = velocity_limited
        applied = command - baseline
        self._previous_residual = applied.copy()
        self._previous_command = command.copy()
        return ProjectionResult(command, applied, False, tuple(reasons))
