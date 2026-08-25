#!/usr/bin/env python3
"""Runtime API for gestures recorded by teach_hand_gestures.py."""

import json
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray


DEFAULT_FILE = Path(__file__).with_name("hand_gestures.json")


class HandGesturePlayer:
    """Publish named L10 gestures to an already running lbot_driver."""

    def __init__(self, gesture_file: str = str(DEFAULT_FILE), robot_namespace: str = "robot1",
                 side: str = "right"):
        self.gesture_file = Path(gesture_file).expanduser()
        self.robot_namespace = robot_namespace.strip("/")
        self.side = side
        self._owns_rclpy = not rclpy.ok()
        if self._owns_rclpy:
            rclpy.init(args=None)
        self._node = Node("hand_gesture_player")
        topic = f"/{self.robot_namespace}/{self.side}_hand/set_l10_joint"
        self._publisher = self._node.create_publisher(UInt8MultiArray, topic, 10)
        self.gestures = self._load_gestures()

    def _load_gestures(self) -> Dict[str, Iterable[int]]:
        if not self.gesture_file.exists():
            raise FileNotFoundError(f"gesture file not found: {self.gesture_file}")
        with self.gesture_file.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
        gestures = data.get("gestures", data)
        if not isinstance(gestures, dict):
            raise ValueError("gesture JSON must contain an object named 'gestures'")
        result = {}
        for name, values in gestures.items():
            if not isinstance(name, str) or not isinstance(values, list) or len(values) != 10:
                raise ValueError(f"gesture '{name}' must contain 10 values")
            if any(not isinstance(value, int) or value < 0 or value > 255 for value in values):
                raise ValueError(f"gesture '{name}' values must be integers in [0, 255]")
            result[name] = values
        return result

    def play(self, name: str, repeat: int = 1, interval: float = 0.05) -> None:
        """Publish a recorded gesture. Repeat helps ensure a remote driver receives it."""
        if name not in self.gestures:
            raise KeyError(f"unknown gesture '{name}', available: {', '.join(self.gestures)}")
        message = UInt8MultiArray()
        message.data = list(self.gestures[name])
        for _ in range(max(1, repeat)):
            self._publisher.publish(message)
            rclpy.spin_once(self._node, timeout_sec=0.0)
            if interval > 0:
                time.sleep(interval)

    def close(self) -> None:
        self._node.destroy_node()
        if self._owns_rclpy and rclpy.ok():
            rclpy.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def execute_gesture(name: str, gesture_file: str = str(DEFAULT_FILE),
                    robot_namespace: str = "robot1", side: str = "right") -> None:
    """One-shot convenience function for another Python script."""
    with HandGesturePlayer(gesture_file, robot_namespace, side) as player:
        player.play(name, repeat=3)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Execute one recorded hand gesture")
    parser.add_argument("name")
    parser.add_argument("--file", default=str(DEFAULT_FILE))
    parser.add_argument("--robot-namespace", default="robot1")
    parser.add_argument("--side", choices=("left", "right"), default="right")
    args = parser.parse_args()
    execute_gesture(args.name, args.file, args.robot_namespace, args.side)
