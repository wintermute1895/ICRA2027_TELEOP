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
    ros_joint_positions,
    validate_action,
    validate_runtime_config,
    validate_state,
    validate_observation_timing,
)


JPEG_QUALITY = 95


def jpeg(msg: Image) -> bytes:
    channels = {"rgb8": 3, "bgr8": 3, "rgba8": 4, "bgra8": 4}.get(msg.encoding)
    if channels is None:
        raise ValueError(f"unsupported image encoding: {msg.encoding}")
    if msg.step != msg.width * channels:
        raise ValueError("ACT camera image has unsupported row padding")
    raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.step)
    image = raw[:, : msg.width * channels].reshape(msg.height, msg.width, channels)
    if msg.encoding.startswith("rgb"):
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR if channels == 3 else cv2.COLOR_RGBA2BGR)
    elif channels == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    if (msg.width, msg.height) != (IMAGE_WIDTH, IMAGE_HEIGHT):
        interpolation = (
            cv2.INTER_AREA
            if msg.width > IMAGE_WIDTH or msg.height > IMAGE_HEIGHT
            else cv2.INTER_LINEAR
        )
        image = cv2.resize(image, (IMAGE_WIDTH, IMAGE_HEIGHT), interpolation=interpolation)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise ValueError("JPEG encoding failed")
    return encoded.tobytes()


class ACTAdapter(Node):
    def __init__(self, config: dict) -> None:
        super().__init__("act_ros_adapter")
        validate_runtime_config(config)
        self.timeout_s = float(config.get("input_timeout_ms", 300.0)) / 1000.0
        self.action_units = config.get("action_units", "radians")
        self.values: dict[str, tuple[float, object]] = {}
        self.camera_keys = dict(config.get("camera_keys") or {})
        self.pending: Future | None = None
        self.pending_started: float | None = None
        self.last_skip_diag = 0.0
        self._reset_next = False
        self._sequence_id = 0
        self.pending_context: dict | None = None
        self.max_observation_skew_ms = float(config.get("max_observation_skew_ms", 100.0))
        self.max_input_age_ms = float(config.get("max_input_age_ms", 250.0))
        self.max_candidate_age_ms = float(config.get("max_candidate_age_ms", 300.0))
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
                if time.monotonic() - self.last_skip_diag >= 1.0:
                    self.last_skip_diag = time.monotonic()
                    self.get_logger().info("[diag] infer in flight")
                return
            try:
                response = self.pending.result()
                context = self.pending_context or {}
                response_age = time.monotonic() - (self.pending_started or time.monotonic())
                timed_out = response_age > self.timeout_s
                if timed_out:
                    response = {"ready": False, "reason": "inference_timeout", "latency_s": response_age}
                plan_receipt_ns = int(response.get("plan_origin_receipt_monotonic_ns") or
                                      context.get("oldest_receipt_ns", time.monotonic_ns()))
                total_age_ms = (time.monotonic_ns() - plan_receipt_ns) / 1e6
                response["total_candidate_age_ms"] = total_age_ms
                response.update(context.get("timing", {}))
                sequence_matches = response.get("inference_sequence_id") == context.get("inference_sequence_id")
                response["sequence_matches"] = sequence_matches
                state = context.get("state")
                if response.get("ready") and state is not None and sequence_matches and total_age_ms <= self.max_candidate_age_ms:
                    candidate = validate_action(response.get("command_rad"))
                    msg = JointState()
                    msg.header = state.header
                    msg.name = list(state.name)
                    msg.position = ros_joint_positions(candidate, self.action_units)
                    self.output_pub.publish(msg)
                    response["published"] = True
                else:
                    response["published"] = False
                    if response.get("ready") and total_age_ms > self.max_candidate_age_ms:
                        response["reason"] = "candidate_stale"
                self.diagnose(**response)
                if timed_out or response.get("ready") is not True:
                    self._reset_next = True
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self._reset_next = True
                self.diagnose(ready=False, reason=f"worker_unavailable:{type(error).__name__}")
            self.pending = None
            self.pending_started = None
            self.pending_context = None
        now = time.monotonic()
        required = ["state", *self.camera_keys]
        missing = [name for name in required if name not in self.values]
        stale = {
            name: round(now - self.values[name][0], 3)
            for name in required
            if name in self.values and now - self.values[name][0] > self.timeout_s
        }
        if missing or stale:
            if now - self.last_skip_diag >= 1.0:
                self.last_skip_diag = now
                self.get_logger().info(
                    f"[diag] infer skipped missing={missing} stale_ages_s={stale}"
                )
                self.diagnose(ready=False, reason="input_missing_or_stale", missing=missing, stale_ages_s=stale)
            return
        snapshots = {name: self.values[name] for name in required}
        state = snapshots["state"][1]
        stamp_ns = {
            name: int(item[1].header.stamp.sec) * 1_000_000_000 + int(item[1].header.stamp.nanosec)
            for name, item in snapshots.items()
        }
        receipt_ns = {name: int(item[0] * 1_000_000_000) for name, item in snapshots.items()}
        ages_ms = {name: (time.monotonic_ns() - value) / 1e6 for name, value in receipt_ns.items()}
        try:
            timing = validate_observation_timing(
                stamp_ns, ages_ms, max_skew_ms=self.max_observation_skew_ms,
                max_age_ms=self.max_input_age_ms)
        except ValueError as error:
            self.diagnose(ready=False, reason="observation_timing_invalid", detail=str(error),
                          input_header_stamps_ns=stamp_ns, input_ages_ms=ages_ms)
            return
        self._sequence_id += 1
        request = {
            "timestamp_ns": stamp_ns["state"],
            "inference_sequence_id": self._sequence_id,
            "state": list(state.position),
            "reset": self._reset_next,
            "oldest_receipt_monotonic_ns": min(receipt_ns.values()),
        }
        self._reset_next = False
        self.pending = self.inference_executor.submit(
            self.exchange,
            request,
            {key: snapshots[key][1] for key in self.camera_keys},
        )
        self.pending_started = now
        self.pending_context = {
            "state": state, "inference_sequence_id": self._sequence_id,
            "oldest_receipt_ns": min(receipt_ns.values()),
            "timing": {**timing, "input_header_stamps_ns": stamp_ns, "input_ages_ms": ages_ms},
        }

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
