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


@dataclass(frozen=True)
class ActiveModelOutcome:
    """Result of one ACT-only active-deployment gate decision.

    ``publish=False`` means the supervisor must not emit any robot command for
    this event; the robot therefore keeps its current state.  State names map
    to the startup sequence requested by operators:

      * WAITING_FOR_MODEL - no accepted ACT command has ever been published
      * ACTIVE_CONTROL    - at least one accepted ACT command was published
    """

    state: str
    publish: bool
    reason: str
    command_rad: np.ndarray | None = None
    first_command: bool = False
    ramp_applied: bool = False


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


class ActiveModelGate:
    """ACT-only startup gate used when ``active_model_control=true``.

    Unlike the legacy fallback path, this gate never forwards teleoperation /
    LinkerTA frames to the bridge.  Before the first accepted ACT candidate it
    returns ``publish=False`` (WAITING_FOR_MODEL); after that it only publishes
    bounded ACT candidates.  The measured robot state is the safety reference
    used by ActionSupervisor, so a command that starts far from the measured
    pose is not emitted.

    This class is ROS-free so the startup sequence can be unit tested offline.
    """

    def __init__(self, *, timeout_s: float, limits: DeploymentLimits,
                 max_step_rate_rad_s: float = 0.0):
        if max_step_rate_rad_s < 0.0:
            raise ValueError("max_step_rate_rad_s must be non-negative")
        self._decider = ActionSupervisor(
            mode=DeploymentMode.ACTIVE,
            timeout_s=timeout_s,
            limits=limits,
        )
        self._max_step_rate_rad_s = float(max_step_rate_rad_s)
        self._published_once = False

    @property
    def state(self) -> str:
        return "ACTIVE_CONTROL" if self._published_once else "WAITING_FOR_MODEL"

    def consider(
        self,
        *,
        base_rad: Iterable[float] | np.ndarray | None,
        candidate_rad: Iterable[float] | np.ndarray | None,
        candidate_time_s: float | None,
        now_s: float,
        previous_rad: Iterable[float] | np.ndarray | None = None,
        last_output_time_s: float | None = None,
    ) -> ActiveModelOutcome:
        """Decide whether one ACT candidate may become a robot command."""
        if base_rad is None:
            return ActiveModelOutcome(self.state, False, "measured_state_unavailable")
        if candidate_rad is None:
            return ActiveModelOutcome(self.state, False, "model_candidate_missing")
        if candidate_time_s is None:
            return ActiveModelOutcome(self.state, False, "model_candidate_missing")
        if now_s - float(candidate_time_s) > self._decider.timeout_s:
            return ActiveModelOutcome(self.state, False, "model_candidate_stale")
        base = np.asarray(base_rad, dtype=np.float32)
        candidate = np.asarray(candidate_rad, dtype=np.float32)
        if base.ndim != 1 or not np.isfinite(base).all():
            return ActiveModelOutcome(self.state, False, "measured_state_invalid")
        if candidate.ndim != 1 or candidate.shape != base.shape or not np.isfinite(candidate).all():
            return ActiveModelOutcome(self.state, False, "model_candidate_invalid")
        decision = self._decider.decide(
            base, candidate,
            candidate_time=candidate_time_s,
            previous_rad=previous_rad,
            now=now_s,
            source="act",
        )
        if not decision.accepted:
            return ActiveModelOutcome(self.state, False, decision.reason)
        command_rad = decision.command_rad.copy()
        ramp_applied = False
        if (self._max_step_rate_rad_s > 0.0 and previous_rad is not None
                and last_output_time_s is not None):
            dt_s = max(now_s - float(last_output_time_s), 0.0)
            step_limit = self._max_step_rate_rad_s * dt_s
            delta = command_rad - np.asarray(previous_rad, dtype=np.float32)
            if np.any(np.abs(delta) > step_limit):
                command_rad = np.asarray(previous_rad, dtype=np.float32) + np.clip(
                    delta, -step_limit, step_limit)
                ramp_applied = True
        first_command = not self._published_once
        self._published_once = True
        return ActiveModelOutcome(
            "ACTIVE_CONTROL",
            True,
            "accepted_ramped" if ramp_applied else "accepted",
            command_rad=command_rad,
            first_command=first_command,
            ramp_applied=ramp_applied,
        )
