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
from robot_teleop.deployment import ActionSupervisor, DeploymentLimits, DeploymentMode  # noqa: E402


class ModelDeploymentSupervisor(Node):
    def __init__(self, config: dict, *, mode_override: str | None = None, source_override: str | None = None) -> None:
        super().__init__("model_deployment_supervisor")
        self.config = config
        self.arm = str(config.get("arm", "right"))
        self.source = str(source_override or config.get("source", "teleop")).lower()
        self.units = str(config.get("input_units", "degrees")).lower()
        self.timeout_s = float(config.get("timeout_ms", 300.0)) / 1000.0
        mode = mode_override or str(config.get("mode", "shadow"))
        self.supervisor = ActionSupervisor(
            mode=DeploymentMode(mode),
            timeout_s=self.timeout_s,
            limits=DeploymentLimits(
                max_delta_rad=float(config.get("max_delta_rad", 0.05)),
                max_step_rad=float(config.get("max_step_rad", 0.05)),
            ),
        )
        self.fallback: tuple[float, JointState] | None = None
        self.candidates: dict[str, tuple[float, JointState]] = {}
        self.previous: np.ndarray | None = None
        self.output_pub = self.create_publisher(JointState, str(config["output_topic"]), 10)
        self.diagnostics_pub = self.create_publisher(String, str(config["diagnostics_topic"]), 10)
        self.create_subscription(JointState, str(config["fallback_topic"]), self.on_fallback, 10)
        for name, topic in (config.get("candidate_topics") or {}).items():
            self.create_subscription(JointState, str(topic), lambda msg, source=name: self.on_candidate(source, msg), 10)

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
        self.diagnostics_pub.publish(String(data=json.dumps(values, separators=(",", ":"))))

    def on_fallback(self, msg: JointState) -> None:
        now = time.monotonic()
        self.fallback = (now, msg)
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
        self.previous = decision.command_rad.copy()
        output = JointState()
        output.header = msg.header
        output.name = list(msg.name)
        values = decision.command_rad
        if self.units in {"degree", "degrees", "deg"}:
            values = np.rad2deg(values)
        output.position = values.astype(float).tolist()
        output.velocity = list(msg.velocity)
        output.effort = list(msg.effort)
        self.output_pub.publish(output)
        self.diagnose(source=decision.source, accepted=decision.accepted, reason=decision.reason,
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
