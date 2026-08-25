#!/usr/bin/env python3
"""Publish L10/O6 gestures to the lbot_driver ROS2 hand command topic.

The current pose is published continuously so a rosbag always contains hand
samples, including when the operator has not changed gesture during an
episode.  Enter ``0``, ``1`` or ``2`` followed by Enter to change the pose;
enter ``q`` to stop the node.

By default it mirrors commands to ``lbot_driver``; ``--direct-can`` also sends
the same commands through the L10 SocketCAN protocol. Do not run it together
with another publisher or CAN hand driver for the same hand.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import queue
import socket
import struct
import sys
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray


class DirectL10Can:
    """Minimal SocketCAN sender using the L10 protocol in this package."""

    def __init__(self, side: str, interface: str):
        self.can_id = 0x27 if side == "right" else 0x28
        self.interface = interface
        self.sock = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        self.sock.bind((interface,))

    def send_frame(self, property_id: int, values: list[int]) -> None:
        payload = bytes([property_id, *values])
        if len(payload) > 8:
            raise ValueError(f"L10 CAN payload too large: {len(payload)}")
        frame = struct.pack("=IB3x8s", self.can_id, len(payload), payload.ljust(8, b"\0"))
        sent = self.sock.send(frame)
        if sent != len(frame):
            raise OSError(f"short CAN frame write: {sent}/{len(frame)} bytes")
        # Match the vendor SDK's 3 ms inter-frame delay. The L10 controller
        # can silently discard adjacent configuration/position frames.
        time.sleep(0.003)

    def initialize(self, value: int = 250) -> None:
        self.send_frame(0x05, [value] * 5)
        self.send_frame(0x06, [value] * 5)
        self.send_frame(0x02, [value] * 5)
        self.send_frame(0x03, [value] * 5)
        time.sleep(0.02)

    def write(self, values: list[int]) -> None:
        if len(values) != 10:
            raise ValueError("L10 position must contain exactly 10 values")
        self.send_frame(0x04, values[6:])
        self.send_frame(0x01, values[:6])

    def close(self) -> None:
        self.sock.close()


def load_gestures(output: str, hand: str) -> dict[int, list[int]]:
    path = Path(output) / f"{hand.lower()}_gestures.json"
    if not path.is_file():
        raise FileNotFoundError(f"gesture file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if str(data.get("hand", "")).upper() != hand.upper():
        raise ValueError(f"gesture file is for {data.get('hand')!r}, not {hand}")
    expected = 10 if hand.upper() == "L10" else 6
    gestures = {}
    for number, values in data.get("gestures", {}).items():
        # The O6 SDK stores angles in 0..100, while lbot_driver's L6 topic
        # accepts the corresponding raw 0..255 byte values.
        scale = 255.0 / 100.0 if hand.upper() == "O6" else 1.0
        gestures[int(number)] = [
            max(0, min(255, int(round(float(value) * scale)))) for value in values
        ]
    if not gestures or any(len(values) != expected for values in gestures.values()):
        raise ValueError(f"all gestures must contain exactly {expected} joints")
    return gestures


class HandPublisher(Node):
    def __init__(
        self,
        topic: str,
        gestures: dict[int, list[int]],
        rate: float,
        hardware: DirectL10Can | None = None,
    ):
        super().__init__("l10_hand_gesture_publisher")
        self.publisher = self.create_publisher(UInt8MultiArray, topic, 10)
        self.speed_publisher = None
        self.force_publisher = None
        joint_suffix = next(
            (suffix for suffix in ("l10", "l6") if topic.endswith(f"/set_{suffix}_joint")),
            None,
        )
        if joint_suffix is not None:
            base = topic[: -len(f"/set_{joint_suffix}_joint")]
            self.speed_publisher = self.create_publisher(
                UInt8MultiArray, f"{base}/set_{joint_suffix}_speed", 10
            )
            self.force_publisher = self.create_publisher(
                UInt8MultiArray, f"{base}/set_{joint_suffix}_force", 10
            )
        self.controls_initialized = False
        self.hardware = hardware
        self.hardware_initialized = False
        self.gestures = gestures
        self.selected = min(gestures)
        self.stop_requested = False
        self._commands: queue.Queue[str] = queue.Queue()
        self._timer = self.create_timer(1.0 / rate, self.publish_pose)
        self.get_logger().info(
            f"publishing {topic} at {rate:g} Hz; initial gesture={self.selected}"
        )

    def set_command_queue(self, commands: queue.Queue[str]) -> None:
        self._commands = commands

    def publish_pose(self) -> None:
        if self.hardware is not None and not self.hardware_initialized:
            self.hardware.initialize()
            self.hardware_initialized = True
            self.get_logger().info(
                f"initialized direct L10 CAN on {self.hardware.interface}"
            )

        # The lbot demo configures these before the first position command;
        # without them some L10 controllers accept the topic but do not move.
        if (
            not self.controls_initialized
            and self.speed_publisher is not None
            and self.force_publisher is not None
            and self.speed_publisher.get_subscription_count() > 0
            and self.force_publisher.get_subscription_count() > 0
        ):
            speed = UInt8MultiArray()
            speed.data = [250] * len(self.gestures[self.selected])
            force = UInt8MultiArray()
            force.data = [250] * len(self.gestures[self.selected])
            self.speed_publisher.publish(speed)
            self.force_publisher.publish(force)
            self.controls_initialized = True
            self.get_logger().info(
                f"initialized {len(self.gestures[self.selected])}-joint hand speed=250 and force=250"
            )

        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                break
            if command == "q":
                self.stop_requested = True
                return
            if command.isdigit() and int(command) in self.gestures:
                self.selected = int(command)
                self.get_logger().info(f"selected gesture={self.selected}")
            else:
                self.get_logger().warning(
                    f"unknown gesture {command!r}; available={sorted(self.gestures)}"
                )
        message = UInt8MultiArray()
        message.data = self.gestures[self.selected]
        self.publisher.publish(message)
        if self.hardware is not None:
            self.hardware.write(self.gestures[self.selected])


def read_commands(commands: queue.Queue[str]) -> None:
    for line in sys.stdin:
        command = line.strip().lower()
        if command:
            commands.put(command)
        if command == "q":
            return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hand", choices=("L10", "O6"), default="O6")
    parser.add_argument("--side", choices=("left", "right"), default="right")
    parser.add_argument("--robot-namespace", default="robot1")
    parser.add_argument("--topic", default=None, help="Override the ROS topic")
    parser.add_argument("--can", default="can0")
    parser.add_argument(
        "--direct-can", action="store_true",
        help="also drive the physical L10 directly via SocketCAN",
    )
    parser.add_argument("--output", default="gestures")
    parser.add_argument("--rate", type=float, default=10.0)
    args = parser.parse_args(argv)
    if args.rate <= 0:
        parser.error("--rate must be greater than zero")

    gestures = load_gestures(args.output, args.hand)
    namespace = args.robot_namespace.strip("/")
    joint_suffix = "l10" if args.hand == "L10" else "l6"
    topic = args.topic or f"/{namespace}/{args.side}_hand/set_{joint_suffix}_joint"
    commands: queue.Queue[str] = queue.Queue()

    if args.direct_can and args.hand != "L10":
        parser.error("--direct-can currently supports L10 only; publish O6 through lbot_driver")
    hardware = DirectL10Can(args.side, args.can) if args.direct_can else None
    rclpy.init()
    node = HandPublisher(topic, gestures, args.rate, hardware)
    node.set_command_queue(commands)
    input_thread = threading.Thread(target=read_commands, args=(commands,), daemon=True)
    input_thread.start()
    print(
        f"{args.hand} 手部 ROS 发布器已启动：输入手势编号回车切换，输入 q 回车退出。",
        flush=True,
    )
    try:
        while rclpy.ok() and not node.stop_requested:
            rclpy.spin_once(node, timeout_sec=0.2)
    except KeyboardInterrupt:
        pass
    except Exception:
        # A ros2 launch shutdown can invalidate the wait set before spin_once
        # returns. Preserve real runtime errors while suppressing that exit.
        if rclpy.ok():
            raise
    finally:
        if hardware is not None:
            hardware.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
