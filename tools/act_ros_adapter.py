#!/usr/bin/env python3
"""ROS2 side of ACT deployment; the model itself runs in the training env."""
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
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Image, JointState
from std_msgs.msg import String
from act_arm7_contract import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    validate_action,
    validate_runtime_config,
    validate_state,
)


def jpeg(msg: Image) -> bytes:
    channels = {"rgb8": 3, "bgr8": 3, "rgba8": 4, "bgra8": 4}.get(msg.encoding)
    if channels is None:
        raise ValueError(f"unsupported image encoding: {msg.encoding}")
    if (msg.width, msg.height) != (IMAGE_WIDTH, IMAGE_HEIGHT):
        raise ValueError(f"ACT camera requires {IMAGE_WIDTH}x{IMAGE_HEIGHT}, got {msg.width}x{msg.height}")
    if msg.step != msg.width * channels:
        raise ValueError("ACT camera image has unsupported row padding")
    raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.step)
    image = raw[:, : msg.width * channels].reshape(msg.height, msg.width, channels)
    if msg.encoding.startswith("rgb"):
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR if channels == 3 else cv2.COLOR_RGBA2BGR)
    elif channels == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ValueError("JPEG encoding failed")
    return encoded.tobytes()


class ACTAdapter(Node):
    def __init__(self, config: dict) -> None:
        super().__init__("act_ros_adapter")
        validate_runtime_config(config)
        self.timeout_s = float(config.get("input_timeout_ms", 300.0)) / 1000.0
        self.values: dict[str, tuple[float, object]] = {}
        self.camera_keys = dict(config.get("camera_keys") or {})
        self.pending: Future | None = None
        self.pending_started: float | None = None
        self.inference_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="act-worker")
        self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connection.settimeout(self.timeout_s)
        self.connection.connect(config["socket"])
        self.stream = self.connection.makefile("rwb")
        self.output_pub = self.create_publisher(JointState, config["output_topic"], 10)
        self.diagnostics_pub = self.create_publisher(String, config["diagnostics_topic"], 10)
        self.create_subscription(JointState, config["state_topic"], self.on_state, 10)
        for key, topic in self.camera_keys.items():
            self.create_subscription(Image, topic, lambda msg, name=key: self.put(name, msg), 2)
        self.create_timer(1.0 / float(config.get("inference_hz", 10.0)), self.infer)

    def put(self, key: str, msg: object) -> None:
        self.values[key] = (time.monotonic(), msg)

    def on_state(self, msg: JointState) -> None:
        try:
            validate_state(msg.position)
        except ValueError as error:
            self.diagnose(ready=False, reason="state_invalid", detail=str(error))
            return
        self.put("state", msg)

    def diagnose(self, **payload: object) -> None:
        self.diagnostics_pub.publish(String(data=json.dumps(payload, separators=(",", ":"))))

    def exchange(self, request: dict, images: dict[str, Image]) -> dict:
        request["camera_jpeg_base64"] = {key: base64.b64encode(jpeg(images[key])).decode() for key in self.camera_keys}
        self.stream.write((json.dumps(request) + "\n").encode())
        self.stream.flush()
        line = self.stream.readline()
        if not line:
            raise OSError("ACT worker disconnected")
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
                self.diagnose(**response)
                state = self.values.get("state")
                if response.get("ready") and state:
                    candidate = validate_action(response.get("command_rad"))
                    msg = JointState()
                    msg.header = state[1].header
                    msg.name = list(state[1].name)
                    msg.position = np.rad2deg(candidate).astype(float).tolist()
                    self.output_pub.publish(msg)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.diagnose(ready=False, reason=f"worker_unavailable:{type(error).__name__}")
            self.pending = None
            self.pending_started = None
        now = time.monotonic()
        required = ["state", *self.camera_keys]
        if any(key not in self.values or now - self.values[key][0] > self.timeout_s for key in required):
            return
        state = self.values["state"][1]
        self.pending = self.inference_executor.submit(
            self.exchange,
            {"timestamp_ns": self.get_clock().now().nanoseconds, "state": list(state.position)},
            {key: self.values[key][1] for key in self.camera_keys},
        )
        self.pending_started = now

    def destroy_node(self) -> None:
        self.inference_executor.shutdown(wait=False, cancel_futures=True)
        self.stream.close()
        self.connection.close()
        super().destroy_node()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    if config.get("enabled") is not True:
        raise SystemExit("ACT adapter is disabled in runtime config")
    rclpy.init()
    node = ACTAdapter(config)
    try:
        rclpy.spin(node)
    except ExternalShutdownException:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
