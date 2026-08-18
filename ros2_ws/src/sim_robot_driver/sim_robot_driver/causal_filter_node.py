"""Simulation-only ROS2 adapter for the causal command-filter v0."""
from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Optional

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from lbot_arm_interfaces.msg import FollowJoint

from .causal_filter import CausalFilterModel, blend_command


class CausalFilterNode(Node):
    def __init__(self) -> None:
        super().__init__("causal_command_filter_v0")
        self.declare_parameter("model_path", "")
        self.declare_parameter("source_namespace", "/teleop")
        self.declare_parameter("state_namespace", "/sim/robot1")
        self.declare_parameter("output_namespace", "/filter_v0")
        self.declare_parameter("blend", 0.5)
        self.declare_parameter("max_correction_rad", 0.08)
        self.declare_parameter("max_ood_z", 3.0)
        model_path = Path(str(self.get_parameter("model_path").value)).expanduser()
        if not model_path.is_file():
            raise FileNotFoundError("filter_enabled requires a valid model_path")
        self.model = CausalFilterModel.load(model_path)
        self.source_namespace = str(self.get_parameter("source_namespace").value).rstrip("/")
        self.state_namespace = str(self.get_parameter("state_namespace").value).rstrip("/")
        self.output_namespace = str(self.get_parameter("output_namespace").value).rstrip("/")
        self.blend = float(self.get_parameter("blend").value)
        self.max_correction_rad = float(self.get_parameter("max_correction_rad").value)
        self.max_ood_z = float(self.get_parameter("max_ood_z").value)
        self.histories = {arm: deque(maxlen=self.model.history_length) for arm in ("left", "right")}
        self.states: dict[str, list[float] | None] = {"left": None, "right": None}
        self.publishers = {arm: self.create_publisher(FollowJoint, f"{self.output_namespace}/{arm}_arm/joint_follow", 20) for arm in self.states}
        self.diagnostics = {arm: self.create_publisher(JointState, f"{self.output_namespace}/{arm}/command", 20) for arm in self.states}
        self.subscriptions = []
        for arm in self.states:
            self.subscriptions.append(self.create_subscription(JointState, f"{self.source_namespace}/{arm}/mapped_joint_command", lambda msg, a=arm: self.command_callback(a, msg), 20))
            self.subscriptions.append(self.create_subscription(JointState, f"{self.state_namespace}/{arm}_arm/joint_states", lambda msg, a=arm: self.state_callback(a, msg), 20))
        self.get_logger().info(f"causal filter v0 ready: model={model_path}, output={self.output_namespace} (simulation only)")

    def state_callback(self, arm: str, msg: JointState) -> None:
        values = [float(value) for value in msg.position]
        if len(values) == self.model.joint_count:
            self.states[arm] = values

    def command_callback(self, arm: str, msg: JointState) -> None:
        values = [float(value) for value in msg.position]
        if len(values) != self.model.joint_count:
            self.get_logger().error(f"{arm} command rejected: expected {self.model.joint_count} joints")
            return
        history = self.histories[arm]
        history.append(values)
        output, diagnostics = values, {"fallback": True}
        if self.states[arm] is not None and len(history) == self.model.history_length:
            try:
                output, diagnostics = blend_command(self.model, list(history), self.states[arm], blend=self.blend, max_correction_rad=self.max_correction_rad, max_ood_z=self.max_ood_z)
            except ValueError as exc:
                self.get_logger().warn(f"{arm} filter fallback: {exc}")
        follow = FollowJoint()
        follow.joints, follow.follow = output, True
        self.publishers[arm].publish(follow)
        observation = JointState()
        observation.header, observation.name, observation.position = msg.header, [f"{arm}_joint_{index + 1}" for index in range(len(output))], output
        self.diagnostics[arm].publish(observation)
        if not diagnostics.get("fallback", True):
            self.get_logger().debug(f"{arm} filter blend={diagnostics['blend']:.3f} ood_z={diagnostics['ood_z']:.3f}")


def main() -> None:
    rclpy.init(); node: Optional[CausalFilterNode] = None
    try:
        node = CausalFilterNode(); rclpy.spin(node)
    finally:
        if node is not None: node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
