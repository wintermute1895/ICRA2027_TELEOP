#!/usr/bin/env python3
"""Replay a fixed joint trajectory into the simulation-only command namespace."""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import JointState

from lbot_arm_interfaces.msg import VendorArmCommand


RIGHT_ARM_JOINTS = [
    "Right_Shoulder_Pitch_Joint",
    "Right_Shoulder_Roll_Joint",
    "Right_Shoulder_Yaw_Joint",
    "Right_Elbow_Pitch_Joint",
    "Right_Wrist_Yaw_Joint",
    "Right_Wrist_Roll_Joint",
    "Right_Wrist_Pitch_Joint",
]


@dataclass(frozen=True)
class TrajectoryPoint:
    time_from_start_s: float
    joints_rad: list[float]


def load_reference_csv(path: Path) -> list[TrajectoryPoint]:
    """Load the repository's fixed-reference CSV format with strict validation."""
    if not path.is_file():
        raise FileNotFoundError(f"reference trajectory not found: {path}")
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        expected_fields = ["sample_index", "time_from_start_s", *RIGHT_ARM_JOINTS]
        if reader.fieldnames != expected_fields:
            raise ValueError(f"unexpected CSV columns: expected {expected_fields}, got {reader.fieldnames}")
        points: list[TrajectoryPoint] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                sample_index = int(row["sample_index"])
                time_from_start_s = float(row["time_from_start_s"])
                joints = [float(row[name]) for name in RIGHT_ARM_JOINTS]
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid reference trajectory row {row_number}") from exc
            if sample_index != len(points):
                raise ValueError(f"row {row_number} sample_index must be {len(points)}, got {sample_index}")
            if not math.isfinite(time_from_start_s) or not all(math.isfinite(value) for value in joints):
                raise ValueError(f"row {row_number} contains non-finite values")
            if points and time_from_start_s <= points[-1].time_from_start_s:
                raise ValueError(f"row {row_number} time_from_start_s must be strictly increasing")
            points.append(TrajectoryPoint(time_from_start_s, joints))
    if len(points) < 2:
        raise ValueError("reference trajectory requires at least two points")
    if abs(points[0].time_from_start_s) > 1e-6:
        raise ValueError("reference trajectory must start at time_from_start_s=0")
    return points


class ReferenceTrajectoryReplayer(Node):
    """Preposition and replay a reference trajectory in a simulation-only namespace."""

    def __init__(self) -> None:
        super().__init__("reference_trajectory_replayer")
        self.declare_parameter("trajectory_csv", "")
        self.declare_parameter("command_namespace", "/sim_reference")
        self.declare_parameter("state_topic", "/sim/robot1/right_arm/joint_states")
        self.declare_parameter("start_delay_s", 1.0)
        self.declare_parameter("start_speed_rad_s", 0.05)
        self.declare_parameter("start_acceleration_rad_s2", 0.05)
        self.declare_parameter("start_tolerance_rad", 0.01)
        self.declare_parameter("playback_rate", 1.0)
        self.declare_parameter("loop", False)
        csv_path = Path(str(self.get_parameter("trajectory_csv").value)).expanduser()
        command_namespace = str(self.get_parameter("command_namespace").value).rstrip("/")
        state_topic = str(self.get_parameter("state_topic").value)
        start_delay_s = float(self.get_parameter("start_delay_s").value)
        self.start_speed_rad_s = float(self.get_parameter("start_speed_rad_s").value)
        self.start_acceleration_rad_s2 = float(self.get_parameter("start_acceleration_rad_s2").value)
        self.start_tolerance_rad = float(self.get_parameter("start_tolerance_rad").value)
        self.playback_rate = float(self.get_parameter("playback_rate").value)
        self.loop = bool(self.get_parameter("loop").value)
        if not command_namespace.startswith("/sim"):
            raise ValueError("command_namespace must start with '/sim' to prevent hardware-topic replay")
        if start_delay_s < 0.0 or not math.isfinite(start_delay_s):
            raise ValueError("start_delay_s must be finite and non-negative")
        if self.playback_rate <= 0.0 or not math.isfinite(self.playback_rate):
            raise ValueError("playback_rate must be finite and positive")
        if self.start_speed_rad_s <= 0.0 or not math.isfinite(self.start_speed_rad_s):
            raise ValueError("start_speed_rad_s must be finite and positive")
        if self.start_acceleration_rad_s2 <= 0.0 or not math.isfinite(self.start_acceleration_rad_s2):
            raise ValueError("start_acceleration_rad_s2 must be finite and positive")
        if self.start_tolerance_rad <= 0.0 or not math.isfinite(self.start_tolerance_rad):
            raise ValueError("start_tolerance_rad must be finite and positive")
        self.points = load_reference_csv(csv_path)
        self.publisher = self.create_publisher(VendorArmCommand, f"{command_namespace}/right_arm/vendor_command", 10)
        self.state_subscription = self.create_subscription(JointState, state_topic, self._state_callback, 10)
        self.latest_state: list[float] | None = None
        self.index = 0
        self.started = False
        self.completed = False
        self.start_command_sent = False
        self.arm_after_ns = self.get_clock().now().nanoseconds + int(start_delay_s * 1e9)
        self.trajectory_start_ns: int | None = None
        self.timer = self.create_timer(0.005, self._tick)
        self.get_logger().info(
            f"simulation-only replay armed: {len(self.points)} right-arm points to "
            f"{command_namespace}/right_arm/vendor_command, start delay={start_delay_s:.2f}s"
        )

    def _state_callback(self, message: JointState) -> None:
        positions_by_name = dict(zip(message.name, message.position))
        if all(name in positions_by_name for name in RIGHT_ARM_JOINTS):
            self.latest_state = [float(positions_by_name[name]) for name in RIGHT_ARM_JOINTS]

    def _publish(self, joints_rad: list[float], mode: int) -> None:
        message = VendorArmCommand()
        message.arm = "right"
        message.joints_rad = joints_rad
        message.mode = mode
        message.speed_rad_s = self.start_speed_rad_s
        message.accel_rad_s2 = self.start_acceleration_rad_s2
        message.source = "simulation_reference_trajectory_replayer"
        self.publisher.publish(message)

    def _tick(self) -> None:
        if self.completed:
            return
        now_ns = self.get_clock().now().nanoseconds
        if now_ns < self.arm_after_ns:
            return
        if self.latest_state is None:
            return
        if not self.start_command_sent:
            self._publish(self.points[0].joints_rad, VendorArmCommand.MODE_MOVEJ)
            self.start_command_sent = True
            self.get_logger().info("moving simulated arm to reference start pose")
            return
        if self.trajectory_start_ns is None:
            max_error = max(abs(actual - target) for actual, target in zip(self.latest_state, self.points[0].joints_rad))
            if max_error > self.start_tolerance_rad:
                return
            self.trajectory_start_ns = now_ns
            self.started = True
            self.get_logger().info("reference start pose reached; replay started")
        elapsed_s = (now_ns - self.trajectory_start_ns) / 1e9 * self.playback_rate
        point = self.points[self.index]
        if elapsed_s < point.time_from_start_s:
            return
        self._publish(point.joints_rad, VendorArmCommand.MODE_FOLLOW)
        self.index += 1
        if self.index < len(self.points):
            return
        if self.loop:
            self.index = 0
            self.start_command_sent = False
            self.trajectory_start_ns = None
            self.arm_after_ns = now_ns
            self.get_logger().info("reference replay completed; restarting because loop=true")
            return
        self.completed = True
        self.get_logger().info("reference replay completed; holding final simulated joint command")


def main() -> None:
    rclpy.init()
    node = ReferenceTrajectoryReplayer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
