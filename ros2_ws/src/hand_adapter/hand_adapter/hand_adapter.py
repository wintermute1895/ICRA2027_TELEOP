#!/usr/bin/env python3
"""Translate platform hand topics to official LinkerHand ROS2 topics."""
from __future__ import annotations

import math

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

MODEL_LENGTHS = {"O6": 6, "L10": 10, "L20LITE": 10}


class HandAdapter(Node):
    """Safety gate and namespace adapter; never opens CAN itself."""

    def __init__(self) -> None:
        super().__init__("hand_adapter")
        self.declare_parameter("robot_namespace", "/robot1")
        self.declare_parameter("left_model", "O6")
        self.declare_parameter("right_model", "L20Lite")
        self.declare_parameter("armed", False)
        self.robot_namespace = str(self.get_parameter("robot_namespace").value).rstrip("/")
        self.models = {
            "left": self._canonical_model(self.get_parameter("left_model").value),
            "right": self._canonical_model(self.get_parameter("right_model").value),
        }
        self.armed = bool(self.get_parameter("armed").value)
        self.command_publishers = {
            arm: self.create_publisher(JointState, f"/cb_{arm}_hand_control_cmd", 10)
            for arm in self.models
        }
        self.state_publishers = {
            arm: self.create_publisher(JointState, f"{self.robot_namespace}/{arm}_hand/joint_states", 10)
            for arm in self.models
        }
        self.command_subscriptions = {
            arm: self.create_subscription(
                JointState, f"{self.robot_namespace}/{arm}_hand/control_cmd",
                lambda msg, selected_arm=arm: self._command_callback(selected_arm, msg), 10)
            for arm in self.models
        }
        self.state_subscriptions = {
            arm: self.create_subscription(
                JointState, f"/cb_{arm}_hand_state",
                lambda msg, selected_arm=arm: self._state_callback(selected_arm, msg), 10)
            for arm in self.models
        }
        self.get_logger().info(
            f"ready: left={self.models['left']}({self._length('left')}), "
            f"right={self.models['right']}({self._length('right')}), armed={self.armed}"
        )
        raw_models = {
            str(self.get_parameter("left_model").value).upper().replace(" ", "").replace("_", ""),
            str(self.get_parameter("right_model").value).upper().replace(" ", "").replace("_", ""),
        }
        if "L20LITE" in raw_models:
            self.get_logger().warn(
                "L20 Lite is routed through the official L10 protocol; verify firmware model and 10-joint order before arming"
            )

    @staticmethod
    def _canonical_model(value: object) -> str:
        normalized = str(value).upper().replace(" ", "").replace("_", "")
        if normalized in MODEL_LENGTHS:
            return normalized
        raise ValueError(f"unsupported hand model: {value}; expected O6, L10, or L20Lite")

    def _length(self, arm: str) -> int:
        return MODEL_LENGTHS[self.models[arm]]

    def _command_callback(self, arm: str, msg: JointState) -> None:
        expected = self._length(arm)
        values = [float(value) for value in msg.position]
        if len(values) != expected or not all(math.isfinite(value) and 0.0 <= value <= 255.0 for value in values):
            self.get_logger().error(f"{arm} hand command rejected: expected {expected} finite values in [0,255]")
            return
        if not self.armed:
            self.get_logger().warn(f"{arm} hand command blocked: adapter armed=false", throttle_duration_sec=2.0)
            return
        command = JointState()
        command.header = msg.header
        command.position = values
        command.velocity = list(msg.velocity) if len(msg.velocity) == expected else [0.0] * expected
        command.effort = list(msg.effort) if len(msg.effort) == expected else [0.0] * expected
        self.command_publishers[arm].publish(command)

    def _state_callback(self, arm: str, msg: JointState) -> None:
        # State is an observation contract, not a command contract.  Physical
        # hands may expose passive or firmware-defined coordinates in addition
        # to their actively driven DoF. Preserve the vendor payload exactly.
        actual = len(msg.position)
        if actual == 0:
            self.get_logger().error(f"{arm} hand state rejected: empty position array")
            return
        state = JointState()
        state.header = msg.header
        state.name = list(msg.name) if len(msg.name) == actual else [f"{arm}_hand_joint_{index + 1}" for index in range(actual)]
        state.position = list(msg.position)
        state.velocity = list(msg.velocity) if len(msg.velocity) == actual else []
        state.effort = list(msg.effort) if len(msg.effort) == actual else []
        self.state_publishers[arm].publish(state)


def main() -> None:
    rclpy.init()
    node = None
    try:
        node = HandAdapter()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
