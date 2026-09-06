"""Small, deterministic safety boundary shared by model deployment adapters."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time
from typing import Iterable

import numpy as np


class DeploymentMode(str, Enum):
    SHADOW = "shadow"
    ACTIVE = "active"


@dataclass(frozen=True)
class DeploymentLimits:
    max_delta_rad: float = 0.05
    max_step_rad: float = 0.05


@dataclass(frozen=True)
class DeploymentDecision:
    command_rad: np.ndarray
    accepted: bool
    source: str
    reason: str


class ActionSupervisor:
    """Validate a model candidate and apply a conservative fallback policy.

    This class is ROS-free so it can be tested independently and reused by ACT
    and learned-filter adapters.  The bridge remains the final mapping/limit
    and hardware gate; this boundary only selects and bounds a candidate.
    """

    def __init__(self, *, mode: DeploymentMode = DeploymentMode.SHADOW,
                 timeout_s: float = 0.3, limits: DeploymentLimits | None = None):
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.mode = DeploymentMode(mode)
        self.timeout_s = float(timeout_s)
        self.limits = limits or DeploymentLimits()
        if self.limits.max_delta_rad < 0 or self.limits.max_step_rad <= 0:
            raise ValueError("invalid deployment limits")

    @staticmethod
    def _vector(value: Iterable[float] | np.ndarray, shape: tuple[int, ...]) -> np.ndarray | None:
        try:
            result = np.asarray(value, dtype=np.float32)
        except (TypeError, ValueError):
            return None
        return result if result.shape == shape and np.isfinite(result).all() else None

    def decide(self, fallback_rad: Iterable[float] | np.ndarray, candidate_rad: Iterable[float] | np.ndarray | None,
               *, candidate_time: float | None = None, previous_rad: Iterable[float] | np.ndarray | None = None,
               now: float | None = None, source: str = "candidate") -> DeploymentDecision:
        now = time.monotonic() if now is None else float(now)
        fallback = np.asarray(fallback_rad, dtype=np.float32)
        if fallback.ndim != 1 or not np.isfinite(fallback).all():
            raise ValueError("fallback command must be a finite vector")
        if self.mode is DeploymentMode.SHADOW:
            return DeploymentDecision(fallback, False, "fallback", "shadow_mode")
        if candidate_rad is None or candidate_time is None or now - float(candidate_time) > self.timeout_s:
            return DeploymentDecision(fallback, False, "fallback", "candidate_stale_or_missing")
        candidate = self._vector(candidate_rad, fallback.shape)
        if candidate is None:
            return DeploymentDecision(fallback, False, "fallback", "candidate_invalid")
        delta = candidate - fallback
        if self.limits.max_delta_rad and np.any(np.abs(delta) > self.limits.max_delta_rad):
            return DeploymentDecision(fallback, False, "fallback", "candidate_delta_exceeded")
        if previous_rad is not None:
            previous = self._vector(previous_rad, fallback.shape)
            if previous is None:
                return DeploymentDecision(fallback, False, "fallback", "previous_invalid")
            if np.any(np.abs(candidate - previous) > self.limits.max_step_rad):
                return DeploymentDecision(fallback, False, "fallback", "candidate_step_exceeded")
        return DeploymentDecision(candidate, True, source, "accepted")
