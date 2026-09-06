#!/usr/bin/env python3
"""Select one model candidate and publish the single bridge input topic.

ACT and learned-filter nodes publish candidates only.  This node is the one
place where a candidate may replace teleoperation input; the bridge remains
the final unit conversion, limit, first-move and armed gate.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rclpy
import yaml
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from robot_teleop.deployment import (  # noqa: E402
    ActiveModelGate,
    ActionSupervisor,
    DeploymentLimits,
    DeploymentMode,
)


class ModelDeploymentSupervisor(Node):
    def __init__(self, config: dict, *, mode_override: str | None = None, source_override: str | None = None) -> None:
        super().__init__("model_deployment_supervisor")
        self.config = config
        self.arm = str(config.get("arm", "right"))
        self.source = str(source_override or config.get("source", "teleop")).lower()
        self.units = str(config.get("input_units", "degrees")).lower()
        self.timeout_s = float(config.get("timeout_ms", 300.0)) / 1000.0
        mode = mode_override or str(config.get("mode", "shadow"))
        self.mode = DeploymentMode(mode)
        self.active_model_control = bool(config.get("active_model_control", False))
        self.max_delta_rad = float(config.get("max_delta_rad", 0.05))
        self.max_step_rad = float(config.get("max_step_rad", 0.05))
        self.max_step_rate_rad_s = float(config.get("max_step_rate_rad_s", 0.0))
        if self.active_model_control:
            if self.mode is not DeploymentMode.ACTIVE:
                raise SystemExit("active_model_control=true requires mode=active")
            if self.source not in {"act", "hybrid", "auto"}:
                raise SystemExit(
                    f"active_model_control=true requires a model candidate source, got source={self.source}")
            if not config.get("state_topic"):
                raise SystemExit("active_model_control=true requires state_topic")
        self.supervisor = ActionSupervisor(
            mode=self.mode,
            timeout_s=self.timeout_s,
            limits=DeploymentLimits(
                max_delta_rad=self.max_delta_rad,
                max_step_rad=self.max_step_rad,
            ),
        )
        self.gate: ActiveModelGate | None = None
        if self.active_model_control:
            self.gate = ActiveModelGate(
                timeout_s=self.timeout_s,
                limits=DeploymentLimits(
                    max_delta_rad=self.max_delta_rad,
                    max_step_rad=self.max_step_rad,
                ),
                max_step_rate_rad_s=self.max_step_rate_rad_s,
            )
        self.last_output_time: float | None = None
        self.fallback: tuple[float, JointState] | None = None
        self.candidates: dict[str, tuple[float, JointState]] = {}
        self.previous: np.ndarray | None = None
        self.measured_rad: np.ndarray | None = None
        self.measured_receipt_time: float | None = None
        self._retry_on_measured = False
        self._last_fallback_suppress_diag = 0.0
        self._started_monotonic = time.monotonic()
        self._last_status_reason: str | None = None
        self._status_published = False
        self.output_pub = self.create_publisher(JointState, str(config["output_topic"]), 10)
        self.diagnostics_pub = self.create_publisher(String, str(config["diagnostics_topic"]), 10)
        self.create_subscription(JointState, str(config["fallback_topic"]), self.on_fallback, 10)
        if config.get("state_topic"):
            self.create_subscription(JointState, str(config["state_topic"]), self.on_state, 10)
        for name, topic in (config.get("candidate_topics") or {}).items():
            self.create_subscription(JointState, str(topic), lambda msg, source=name: self.on_candidate(source, msg), 10)
        if self.active_model_control:
            self.create_timer(5.0, self._status_timer_callback)
        if self.active_model_control:
            self.get_logger().info(
                "state=WAITING_FOR_MODEL fallback suppressed because active model deployment "
                f"(mode={self.mode.value} source={self.source})")

    def _positions_rad(self, msg: JointState) -> np.ndarray | None:
        try:
            values = np.asarray(msg.position, dtype=np.float32)
        except (TypeError, ValueError):
            return None
        if self.units in {"degree", "degrees", "deg"}:
            values = np.deg2rad(values)
        return values

    def on_candidate(self, source: str, msg: JointState) -> None:
        self.candidates[source] = (time.monotonic(), msg)
        self._publish_active_if_ready()

    def on_state(self, msg: JointState) -> None:
        """Cache the measured robot state; never converts units."""
        try:
            values = np.asarray(msg.position, dtype=np.float32)
        except (TypeError, ValueError):
            values = np.asarray([], dtype=np.float32)
        if values.ndim == 1 and values.size >= 7 and np.isfinite(values).all():
            # Driver initialization can emit one all-zero placeholder before
            # the controller stream arrives.  A real 7-DOF pose is never
            # exactly all-zero, so skip that single placeholder.
            if np.max(np.abs(values[:7])) > 1e-9:
                self.measured_rad = values[:7].copy()
                self.measured_receipt_time = time.monotonic()
                if self._retry_on_measured:
                    self._retry_on_measured = False
                    self._publish_active_if_ready()
        else:
            self.get_logger().warning(
                f"ignoring invalid measured state on {self.config.get('state_topic', '')}")

    def _active_candidate(self, now: float) -> tuple[str, float, JointState] | None:
        selected = self._candidate(now)
        if selected is None:
            return None
        source, candidate_time, candidate_msg = selected
        if source not in {"act", "filter"}:
            # Active model control only forwards explicit model candidates.
            return None
        candidate_rad = self._positions_rad(candidate_msg)
        if candidate_rad is None or candidate_rad.ndim != 1 or candidate_rad.size < 7:
            return None
        return source, candidate_time, candidate_msg

    def _publish_active_if_ready(self) -> None:
        if not self.active_model_control or self.gate is None:
            return
        now = time.monotonic()
        selected = self._active_candidate(now)
        measured = None
        measured_available = (
            self.measured_rad is not None
            and self.measured_receipt_time is not None
            and now - self.measured_receipt_time <= self.timeout_s
        )
        if measured_available:
            measured = self.measured_rad
        candidate = None
        candidate_time = None
        candidate_msg = None
        candidate_source = None
        if selected is not None:
            candidate_source, candidate_time, candidate_msg = selected
            candidate = self._positions_rad(candidate_msg)
        outcome = self.gate.consider(
            base_rad=measured,
            candidate_rad=candidate,
            candidate_time_s=candidate_time,
            now_s=now,
            previous_rad=self.previous,
            last_output_time_s=self.last_output_time,
        )
        if not outcome.publish:
            if outcome.reason == "measured_state_unavailable":
                self._retry_on_measured = True
            self.diagnose(
                state=outcome.state,
                source=candidate_source or "none",
                accepted=False,
                reason=outcome.reason,
                measured_available=measured_available,
                candidate_source=candidate_source,
                published=False,
            )
            return
        if candidate_msg is None or candidate is None:
            self.diagnose(state=outcome.state, source="act", accepted=False,
                          reason="internal_candidate_missing", published=False)
            return
        command_rad = outcome.command_rad.copy()
        self.previous = command_rad.copy()
        self.last_output_time = now
        output = JointState()
        output.header = candidate_msg.header
        output.name = list(candidate_msg.name)
        values = command_rad
        if self.units in {"degree", "degrees", "deg"}:
            values = np.rad2deg(values)
        output.position = values.astype(float).tolist()
        output.velocity = list(candidate_msg.velocity)
        output.effort = list(candidate_msg.effort)
        self.output_pub.publish(output)
        if outcome.first_command:
            self.get_logger().info(
                "first valid ACT command received "
                f"timestamp={candidate_msg.header.stamp.sec}.{candidate_msg.header.stamp.nanosec:09d} "
                f"q_model_rad={np.round(command_rad, 6).tolist()} "
                f"q_model_deg={np.round(np.rad2deg(command_rad), 4).tolist()} "
                f"measured_rad={None if measured is None else np.round(measured, 6).tolist()}")
        self.diagnose(
            state=outcome.state,
            source="act",
            accepted=True,
            reason=outcome.reason,
            published=True,
            first_command=outcome.first_command,
            ramp_applied=outcome.ramp_applied,
            measured_available=measured_available,
            candidate_source=candidate_source,
            dimension=int(command_rad.size),
        )

    def _candidate(self, now: float) -> tuple[str, float, JointState] | None:
        if self.source in {"teleop", "fallback", "none"}:
            return None
        if self.source in {"filter", "act"}:
            item = self.candidates.get(self.source)
            return (self.source, *item) if item else None
        # hybrid/auto selects the newest source; source names remain config-driven.
        available = [(name, stamp, msg) for name, (stamp, msg) in self.candidates.items()]
        return max(available, key=lambda item: item[1]) if available else None

    def diagnose(self, **values: object) -> None:
        values.setdefault("stamp_monotonic", time.monotonic())
        if "reason" in values:
            self._last_status_reason = str(values["reason"])
        if values.get("published") and self.gate is not None and self.gate.state == "ACTIVE_CONTROL":
            self._status_published = True
        self.diagnostics_pub.publish(String(data=json.dumps(values, separators=(",", ":"))))

    def _status_timer_callback(self) -> None:
        if not self.active_model_control:
            return
        now = time.monotonic()
        measured_ok = bool(
            self.measured_rad is not None
            and self.measured_receipt_time is not None
            and now - self.measured_receipt_time <= self.timeout_s
        )
        candidate_age_s = None
        if self.candidates:
            candidate_age_s = now - max(stamp for stamp, _ in self.candidates.values())
        state = self.gate.state if self.gate is not None else "WAITING_FOR_MODEL"
        self.get_logger().info(
            f"state={state} elapsed={now - self._started_monotonic:.0f}s "
            f"measured_ok={str(measured_ok).lower()} "
            f"model_candidate_age_s={candidate_age_s if candidate_age_s is not None else 'none'} "
            f"last_reason={self._last_status_reason or 'none'} "
            f"published_first={str(self._status_published).lower()}")

    def on_fallback(self, msg: JointState) -> None:
        now = time.monotonic()
        self.fallback = (now, msg)
        if self.active_model_control:
            # ACT-only deployment: teleoperation / LinkerTA frames are never
            # forwarded as robot targets.  Keeping the cache warm preserves
            # legacy tooling, but no command is published here.
            if now - self._last_fallback_suppress_diag >= 1.0:
                self._last_fallback_suppress_diag = now
                self.diagnose(
                    state=self.gate.state if self.gate is not None else "WAITING_FOR_MODEL",
                    source="fallback",
                    accepted=False,
                    reason="fallback_suppressed_active_model_control",
                    published=False,
                )
            return
        fallback = self._positions_rad(msg)
        if fallback is None or fallback.ndim != 1 or not np.isfinite(fallback).all():
            self.diagnose(source="fallback", accepted=False, reason="fallback_invalid")
            return
        selected = self._candidate(now)
        candidate = None
        candidate_time = None
        source = "fallback"
        if selected is not None:
            source, candidate_time, candidate_msg = selected
            candidate = self._positions_rad(candidate_msg)
        decision = self.supervisor.decide(
            fallback, candidate, candidate_time=candidate_time, previous_rad=self.previous, now=now, source=source
        )
        command_rad = decision.command_rad.copy()
        reason = decision.reason
        if decision.accepted and self.max_step_rate_rad_s > 0.0 and self.previous is not None and self.last_output_time is not None:
            dt_s = max(now - self.last_output_time, 0.0)
            step_limit = self.max_step_rate_rad_s * dt_s
            delta = command_rad - self.previous
            if np.any(np.abs(delta) > step_limit):
                command_rad = self.previous + np.clip(delta, -step_limit, step_limit)
                reason = "accepted_ramped"
        self.previous = command_rad.copy()
        self.last_output_time = now
        output = JointState()
        output.header = msg.header
        output.name = list(msg.name)
        values = command_rad
        if self.units in {"degree", "degrees", "deg"}:
            values = np.rad2deg(values)
        output.position = values.astype(float).tolist()
        output.velocity = list(msg.velocity)
        output.effort = list(msg.effort)
        self.output_pub.publish(output)
        self.diagnose(source=decision.source, accepted=decision.accepted, reason=reason,
                      candidate_source=source, dimension=int(fallback.size))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--mode", choices=["shadow", "active"])
    parser.add_argument("--source", choices=["teleop", "fallback", "none", "filter", "act", "hybrid", "auto"])
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    if config.get("schema") != "robot_teleop.model-deployment/v1":
        raise SystemExit("unsupported model deployment config schema")
    if config.get("enabled") is not True:
        raise SystemExit("model deployment is disabled in runtime config")
    mode = args.mode or str(config.get("mode", "shadow"))
    if mode == "active" and args.confirm != "I_UNDERSTAND_MODEL_DEPLOYMENT":
        raise SystemExit("active deployment requires --confirm=I_UNDERSTAND_MODEL_DEPLOYMENT")
    rclpy.init()
    node = ModelDeploymentSupervisor(config, mode_override=mode, source_override=args.source)
    # rclpy's RcutilsLogger accepts one already-formatted message; it does
    # not implement the stdlib logger's printf-style positional arguments.
    node.get_logger().info(
        f"deployment supervisor: mode={mode} source={node.source} output={config['output_topic']}"
    )
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
