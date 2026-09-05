#!/usr/bin/env python3
"""Republish one RGB image topic after a horizontal (left-right) flip.

This node is a preview-only helper: the source topic is left untouched and the
flipped topic is never added to the rosbag recorder's topic list. It only
supports tightly packed monochrome/RGB/RGBA sensor_msgs/Image messages, which
is what the capture RealSense color topics publish.
"""
from __future__ import annotations

import argparse

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image


# encoding -> bytes per pixel for tightly packed images
SUPPORTED_ENCODINGS = {
    "mono8": 1,
    "8UC1": 1,
    "rgb8": 3,
    "bgr8": 3,
    "rgba8": 4,
    "bgra8": 4,
    "16UC1": 2,
    "32FC1": 4,
}


class CameraImageHFlip(Node):
    def __init__(self, source: str, target: str) -> None:
        super().__init__("camera_preview_hflip")
        # Best-effort receive connects to both reliable and best-effort camera
        # publishers; publishing reliable matches rqt_image_view's default.
        receive_qos = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
        )
        publish_qos = QoSProfile(
            depth=2,
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
        )
        self._publisher = self.create_publisher(Image, target, publish_qos)
        self.create_subscription(Image, source, self._on_image, receive_qos)
        self.get_logger().info(
            f"horizontal flip relay ready: {source} -> {target}"
        )

    def _on_image(self, message: Image) -> None:
        bytes_per_pixel = SUPPORTED_ENCODINGS.get(message.encoding)
        if bytes_per_pixel is None:
            self.get_logger().warn(
                f"unsupported image encoding, skipping frame: {message.encoding}",
                throttle_duration_sec=5.0,
            )
            return
        expected_step = message.width * bytes_per_pixel
        if message.step != expected_step or len(message.data) != expected_step * message.height:
            self.get_logger().warn(
                f"unexpected step={message.step} size={len(message.data)}; "
                f"expected step={expected_step}; skipping padded/odd frame",
                throttle_duration_sec=5.0,
            )
            return
        raw = np.frombuffer(message.data, dtype=np.uint8)
        image = raw.reshape(int(message.height), int(message.width), bytes_per_pixel)
        flipped = image[:, ::-1, :].copy()
        output = Image()
        output.header = message.header
        output.height = message.height
        output.width = message.width
        output.encoding = message.encoding
        output.is_bigendian = message.is_bigendian
        output.step = message.step
        output.data = flipped.tobytes()
        self._publisher.publish(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="source RGB image topic")
    parser.add_argument("--target", help="flipped RGB image topic (default: SOURCE_mirrored)")
    args = parser.parse_args(argv)
    source = args.source.rstrip("/")
    target = (args.target or f"{source}_mirrored").rstrip("/")
    rclpy.init(args=[])
    node = CameraImageHFlip(source, target)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
