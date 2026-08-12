#!/usr/bin/env python3
"""Keyboard source for simulation-only arm motion and hand grasp presets."""
from __future__ import annotations
import select
import sys
import termios
import tty
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


HAND_PRESETS = {
    # Values use the official SDK's 0..255 command domain, not radians.
    "L10": {
        "open": [255.0, 200.0, 255.0, 255.0, 255.0, 255.0, 180.0, 180.0, 180.0, 41.0],
        "power_grasp": [90.0, 135.0, 20.0, 20.0, 20.0, 20.0, 128.0, 128.0, 128.0, 128.0],
    },
    "O6": {
        "open": [200.0, 255.0, 255.0, 255.0, 255.0, 180.0],
        "power_grasp": [90.0, 135.0, 20.0, 20.0, 20.0, 20.0],
    },
}

class KeyboardMaster(Node):
    def __init__(self) -> None:
        super().__init__("keyboard_master")
        self.declare_parameter("step_deg", 2.0)
        self.declare_parameter("command_namespace", "/robot1")
        self.declare_parameter("left_hand_model", "L10")
        self.declare_parameter("right_hand_model", "L10")
        self.step_deg = float(self.get_parameter("step_deg").value)
        self.command_namespace = str(self.get_parameter("command_namespace").value).rstrip("/")
        self.hand_models = {
            "left": str(self.get_parameter("left_hand_model").value).upper(),
            "right": str(self.get_parameter("right_hand_model").value).upper(),
        }
        if any(model not in HAND_PRESETS for model in self.hand_models.values()):
            raise ValueError("left_hand_model and right_hand_model must be L10 or O6")
        self.arm, self.joint = "left", 0
        self.values = {"left": [0.0] * 7, "right": [0.0] * 7}
        self.hand_mode = {arm: "open" for arm in self.values}
        self.arm_publishers = {
            arm: self.create_publisher(JointState, f"/{arm}_arm_joint_control", 10)
            for arm in self.values
        }
        self.hand_publishers = {
            arm: self.create_publisher(JointState, f"{self.command_namespace}/{arm}_hand/control_cmd", 10)
            for arm in self.values
        }
        self.old_settings = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        self.timer = self.create_timer(0.02, self.poll)
        self.get_logger().info(
            "keyboard master: 1..7 select arm joint; a/d -/+; Tab switch arm; r reset arm; "
            "Space toggle hand open/power_grasp; o open; g grasp; q quit. Arm units=deg, hand units=SDK [0,255]."
        )

    def _publish_hand(self, arm: str, preset: str) -> None:
        model = self.hand_models[arm]
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = [f"{model.lower()}_channel_{index + 1}" for index in range(len(HAND_PRESETS[model][preset]))]
        msg.position = HAND_PRESETS[model][preset]
        self.hand_publishers[arm].publish(msg)
        self.hand_mode[arm] = preset
        self.get_logger().info(f"{arm} {model} hand -> {preset}")

    def poll(self) -> None:
        if not select.select([sys.stdin], [], [], 0.0)[0]:
            return
        key = sys.stdin.read(1)
        if key == " ":
            target = "power_grasp" if self.hand_mode[self.arm] == "open" else "open"
            self._publish_hand(self.arm, target)
            return
        if key == "g":
            self._publish_hand(self.arm, "power_grasp")
            return
        if key == "o":
            self._publish_hand(self.arm, "open")
            return
        if key in "1234567":
            self.joint = int(key) - 1
        elif key == "\t":
            self.arm = "right" if self.arm == "left" else "left"
            self.get_logger().info(f"active arm -> {self.arm}")
            return
        elif key == "a":
            self.values[self.arm][self.joint] -= self.step_deg
        elif key == "d":
            self.values[self.arm][self.joint] += self.step_deg
        elif key == "r":
            self.values[self.arm] = [0.0] * 7
        elif key == "q":
            rclpy.shutdown()
            return
        else:
            return
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = [f"master_joint_{i + 1}" for i in range(7)]
        msg.position = self.values[self.arm]
        self.arm_publishers[self.arm].publish(msg)
        self.get_logger().info(f"{self.arm} J{self.joint + 1} = {self.values[self.arm][self.joint]:+.1f} deg")

    def destroy_node(self) -> bool:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.old_settings)
        return super().destroy_node()


def main() -> None:
    rclpy.init()
    node = None
    try:
        node = KeyboardMaster()
        rclpy.spin(node)
    finally:
        if node is not None: node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
