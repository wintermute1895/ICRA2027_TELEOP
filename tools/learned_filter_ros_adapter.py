#!/usr/bin/python3
"""Transparent ROS2 filter between LinkerTA and teleop_control_bridge."""
from __future__ import annotations

import argparse
import base64
import json
import socket
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import rclpy
import yaml
from rclpy.node import Node
from sensor_msgs.msg import Image, JointState
from std_msgs.msg import String


def jpeg(message: Image) -> bytes:
    channels = {"rgb8": 3, "bgr8": 3, "rgba8": 4, "bgra8": 4}.get(message.encoding)
    if channels is None:
        raise ValueError(f"unsupported image encoding: {message.encoding}")
    raw = np.frombuffer(message.data, dtype=np.uint8).reshape(message.height, message.step)
    image = raw[:, :message.width * channels].reshape(message.height, message.width, channels)
    if message.encoding.startswith("rgb"):
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR if channels == 3 else cv2.COLOR_RGBA2BGR)
    elif channels == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ValueError("JPEG encoding failed")
    return encoded.tobytes()


def joint_state(source: JointState, positions: np.ndarray) -> JointState:
    result = JointState()
    result.header = source.header
    result.name = list(source.name)
    result.position = positions.tolist()
    result.velocity = list(source.velocity)
    result.effort = list(source.effort)
    return result


class Adapter(Node):
    def __init__(self, config: dict) -> None:
        super().__init__("learned_filter_ros_adapter")
        self.timeout_s = float(config.get("input_timeout_ms", 300.0)) / 1000.0
        self.values: dict[str, tuple[float, object]] = {}
        self.camera_ids = [item["id"] for item in config["cameras"]]
        self.pending: Future | None = None
        self.pending_started: float | None = None
        self.master_message: JointState | None = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="learned-filter")

        self.output_pub = self.create_publisher(JointState, config["master_output_topic"], 10)
        self.raw_pub = self.create_publisher(JointState, config["raw_observation_topic"], 10)
        self.filtered_pub = self.create_publisher(JointState, config["filtered_observation_topic"], 10)
        self.diagnostics_pub = self.create_publisher(String, config["diagnostics_topic"], 10)
        self.create_subscription(JointState, config["master_input_topic"], self.on_master, 10)
        self.create_subscription(JointState, config["state_topic"], lambda msg: self.put("state", msg), 10)
        for camera in config["cameras"]:
            self.create_subscription(Image, camera["topic"], lambda msg, name=camera["id"]: self.put(name, msg), 2)

        self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connection.settimeout(self.timeout_s)
        self.connection.connect(config["socket"])
        self.stream = self.connection.makefile("rwb")
        self.create_timer(1.0 / float(config.get("inference_hz", 5.0)), self.infer)

    def put(self, name: str, message: object) -> None:
        self.values[name] = (time.monotonic(), message)

    def diagnose(self, **values: object) -> None:
        self.diagnostics_pub.publish(String(data=json.dumps(values, separators=(",", ":"))))

    def on_master(self, message: JointState) -> None:
        now = time.monotonic()
        raw_rad = np.deg2rad(np.asarray(message.position, dtype=np.float32))
        self.values["master"] = (now, raw_rad)
        self.master_message = message

        self.raw_pub.publish(joint_state(message, raw_rad))
        self.filtered_pub.publish(joint_state(message, raw_rad))

    def exchange(self, request: dict, images: dict[str, Image]) -> dict:
        request["camera_jpeg_base64"] = {
            name: base64.b64encode(jpeg(images[name])).decode() for name in self.camera_ids
        }
        self.stream.write((json.dumps(request) + "\n").encode())
        self.stream.flush()
        line = self.stream.readline()
        if not line:
            raise OSError("learned-filter worker disconnected")
        return json.loads(line)

    def infer(self) -> None:
        if self.pending is not None:
            if not self.pending.done():
                return
            try:
                response = self.pending.result()
                response_age = time.monotonic() - (self.pending_started or time.monotonic())
                if response_age > self.timeout_s:
                    response = {"ready": False, "reason": "inference_timeout", "latency_s": response_age}
                if response.get("ready") is True:
                    if self.master_message is not None:
                        candidate = np.asarray(response.get("command_rad"), dtype=np.float32)
                        if candidate.shape == np.asarray(self.master_message.position).shape and np.isfinite(candidate).all():
                            self.output_pub.publish(joint_state(self.master_message, np.rad2deg(candidate)))
                else:
                    pass
                self.diagnose(**response)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.diagnose(ready=False, reason=f"worker_unavailable:{type(error).__name__}")
            self.pending = None
            self.pending_started = None

        names = ["master", "state", *self.camera_ids]
        now = time.monotonic()
        if any(name not in self.values or now - self.values[name][0] > self.timeout_s for name in names):
            return
        master = self.values["master"][1]
        state = self.values["state"][1]
        images = {name: self.values[name][1] for name in self.camera_ids}
        request = {
            "timestamp_ns": self.get_clock().now().nanoseconds,
            "master_joint_raw_rad": master.tolist(),
            "robot_joint_state_rad": list(state.position),
        }
        self.pending = self.executor.submit(self.exchange, request, images)
        self.pending_started = now

    def destroy_node(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.stream.close()
        self.connection.close()
        super().destroy_node()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    if config.get("enabled") is not True:
        raise SystemExit("learned filter is disabled in runtime config")
    rclpy.init()
    node = Adapter(config)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
