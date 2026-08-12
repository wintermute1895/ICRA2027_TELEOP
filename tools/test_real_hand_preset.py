#!/usr/bin/python3
"""One-step, operator-confirmed LinkerHand preset test through the ROS2 adapter.

This tool sends no CAN frame itself. It publishes the unified platform topic;
the already-running official SDK backend owns CAN, motor limits, and faults.
"""
from __future__ import annotations

import argparse
import math
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


PRESETS = {
    "L10": {
        "open": [255, 200, 255, 255, 255, 255, 180, 180, 180, 41],
        "power_grasp": [90, 135, 20, 20, 20, 20, 128, 128, 128, 128],
    },
    "O6": {
        "open": [200, 255, 255, 255, 255, 180],
        "power_grasp": [90, 135, 20, 20, 20, 20],
    },
}


def parse_values(text: str, count: int) -> list[float]:
    try:
        values = [float(value.strip()) for value in text.split(",") if value.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--positions must be comma-separated numbers") from exc
    if len(values) != count or not all(math.isfinite(value) and 0.0 <= value <= 255.0 for value in values):
        raise argparse.ArgumentTypeError(f"--positions must contain {count} finite values in [0,255]")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("left", "right"), required=True)
    parser.add_argument("--model", choices=("L10", "O6"), required=True)
    parser.add_argument("--preset", choices=("open", "power_grasp", "custom"), required=True)
    parser.add_argument("--positions", help="required only with --preset custom")
    parser.add_argument("--speed", type=float, default=40.0, help="official SDK [0,255] speed applied to every channel (default: 40)")
    parser.add_argument("--force", type=float, default=40.0, help="official SDK [0,255] force/torque applied to every channel (default: 40)")
    parser.add_argument("--state-timeout-s", type=float, default=3.0)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--physical-estop-ready", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    count = len(PRESETS[args.model]["open"])
    if args.preset == "custom":
        if args.positions is None:
            parser.error("--positions is required for --preset custom")
        positions = parse_values(args.positions, count)
    else:
        if args.positions is not None:
            parser.error("--positions is only valid for --preset custom")
        positions = [float(value) for value in PRESETS[args.model][args.preset]]
    for name, value in (("--speed", args.speed), ("--force", args.force)):
        if not math.isfinite(value) or value < 10.0 or value > 255.0:
            parser.error(f"{name} must be in [10,255]")
    topic = f"/robot1/{args.arm}_hand/control_cmd"
    state_topic = f"/robot1/{args.arm}_hand/joint_states"
    plan = {"topic": topic, "state_topic": state_topic, "model": args.model, "preset": args.preset, "position": positions, "speed": args.speed, "force": args.force}
    if not args.execute:
        print({"mode": "dry_run", "plan": plan, "note": "No ROS node or command was created. Start the official SDK + hand_adapter armed=false, verify state, then re-run with the explicit confirmations."})
        return 0
    if not args.physical_estop_ready or args.confirm != "EXECUTE_ONE_HAND_PRESET_WITH_ESTOP_READY":
        raise SystemExit("execution requires --physical-estop-ready and --confirm EXECUTE_ONE_HAND_PRESET_WITH_ESTOP_READY")
    rclpy.init()
    node = Node("real_hand_preset_test")
    received: list[JointState] = []
    node.create_subscription(JointState, state_topic, lambda message: received.append(message), 10)
    publisher = node.create_publisher(JointState, topic, 10)
    deadline = time.monotonic() + args.state_timeout_s
    while time.monotonic() < deadline and not received:
        rclpy.spin_once(node, timeout_sec=0.1)
    if not received:
        node.destroy_node(); rclpy.shutdown()
        raise SystemExit(f"no state received on {state_topic}; SDK/adapter is not ready, command not sent")
    if len(received[-1].position) != count:
        node.destroy_node(); rclpy.shutdown()
        raise SystemExit(f"state length mismatch on {state_topic}: expected {count}, got {len(received[-1].position)}; command not sent")
    command = JointState()
    command.header.stamp = node.get_clock().now().to_msg()
    command.name = [f"{args.model.lower()}_channel_{index + 1}" for index in range(count)]
    command.position = positions
    command.velocity = [args.speed] * count
    command.effort = [args.force] * count
    publisher.publish(command)
    for _ in range(5):
        rclpy.spin_once(node, timeout_sec=0.05)
    node.destroy_node(); rclpy.shutdown()
    print({"mode": "executed_once", "plan": plan, "state_before": list(received[-1].position), "note": "Command was published once through hand_adapter. Inspect the hand and official SDK state/fault output before another command."})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
