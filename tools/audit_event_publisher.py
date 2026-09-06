#!/usr/bin/env python3
"""Publish newline-delimited audit-event JSON received on stdin to ROS2."""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="/teleop/events")
    args = parser.parse_args()
    import rclpy
    from std_msgs.msg import String

    rclpy.init()
    node = rclpy.create_node("teleop_audit_event_publisher")
    publisher = node.create_publisher(String, args.topic, 10)
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            message = String()
            message.data = line.rstrip("\n")
            publisher.publish(message)
            # Spin briefly so DDS can dispatch the sample before the next key.
            rclpy.spin_once(node, timeout_sec=0.01)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
