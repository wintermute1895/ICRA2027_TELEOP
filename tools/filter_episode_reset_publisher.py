#!/usr/bin/env python3
"""Publish one durable episode-reset pulse to the learned-filter adapter."""
from __future__ import annotations

import argparse
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--timeout-s", type=float, default=2.0)
    parser.add_argument("--publish-count", type=int, default=10)
    args = parser.parse_args()
    if args.timeout_s <= 0.0 or args.publish_count < 1:
        raise SystemExit("timeout-s must be positive and publish-count must be >= 1")

    rclpy.init()
    node = Node("filter_episode_reset_publisher")
    qos = QoSProfile(
        depth=10,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )
    publisher = node.create_publisher(Bool, args.topic, qos)
    deadline = time.monotonic() + args.timeout_s
    while publisher.get_subscription_count() < 1 and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    if publisher.get_subscription_count() < 1:
        node.get_logger().error(f"no subscriber matched {args.topic}")
        node.destroy_node()
        rclpy.shutdown()
        return 2

    message = Bool(data=True)
    for _ in range(args.publish_count):
        publisher.publish(message)
        rclpy.spin_once(node, timeout_sec=0.01)
        time.sleep(0.02)
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
