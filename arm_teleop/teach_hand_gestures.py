#!/usr/bin/env python3
"""Interactive keyboard teach pendant for the right L10 hand."""

import argparse
import json
import os
import select
import sys
import termios
import time
import tty
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray


JOINT_NAMES = [
    "thumb_base", "thumb_side", "index_base", "middle_base", "ring_base",
    "pinky_base", "index_side", "ring_side", "pinky_side", "thumb_rotate",
]
OPEN = [250, 128, 250, 250, 250, 250, 128, 128, 128, 250]


class HandPublisher(Node):
    def __init__(self, robot_namespace: str, side: str):
        super().__init__("hand_gesture_teach")
        topic = f"/{robot_namespace.strip('/')}/{side}_hand/set_l10_joint"
        self.publisher = self.create_publisher(UInt8MultiArray, topic, 10)

    def publish_pose(self, pose):
        message = UInt8MultiArray()
        message.data = [int(value) for value in pose]
        self.publisher.publish(message)
        rclpy.spin_once(self, timeout_sec=0.0)


def read_key():
    """Read one key, translating terminal arrow escape sequences."""
    fd = sys.stdin.fileno()
    first = os.read(fd, 1)
    if first != b"\x1b":
        return first.decode("utf-8", errors="ignore")
    # Arrow keys arrive as ESC [ A/B/C/D (or ESC O A/B/C/D). The
    # inter-byte delay can be noticeable in a desktop terminal, so wait
    # briefly for the complete sequence before treating ESC as exit.
    sequence = bytearray()
    deadline = time.monotonic() + 0.2
    while len(sequence) < 8:
        remaining = max(0.0, deadline - time.monotonic())
        if not select.select([fd], [], [], remaining)[0]:
            # No byte after ESC means the user pressed the standalone Esc key.
            return "ESC" if not sequence else "UNKNOWN"
        sequence.extend(os.read(fd, 1))
        if sequence and sequence[-1:] in (b"A", b"B", b"C", b"D"):
            if sequence[:1] in (b"[", b"O"):
                return {b"A": "UP", b"B": "DOWN", b"C": "RIGHT", b"D": "LEFT"}[sequence[-1:]]
            return "UNKNOWN"
    return "UNKNOWN"


def save_gestures(path: Path, gestures):
    payload = {
        "hand_type": "l10",
        "joint_names": JOINT_NAMES,
        "gestures": gestures,
    }
    with path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def clear_screen():
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()


def draw(mode, pose, selected, step, gestures, output_file):
    clear_screen()
    print("L10 手势示教器")
    print("=" * 60)
    print("r: 开始/重新调节    1-9/0: 选择自由度    Enter: 保存标签    Esc: 保存并退出")
    print("方向键: 调节角度    [ / ]: 调整步长    - / +: 单步调节")
    print(f"状态: {mode}    当前自由度: {selected + 1} ({JOINT_NAMES[selected]})    步长: {step}")
    print(f"当前角度: {pose}")
    print("当前已保存: " + (", ".join(gestures) if gestures else "无"))
    print(f"保存文件: {output_file}")
    if mode == "idle":
        print("\n按 r 开始调节。")
    else:
        print("\n调节中，手会实时跟随当前角度。")


def ask_label():
    """Temporarily leave raw mode to read a gesture label."""
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, ORIGINAL_TERMIOS)
    try:
        return input("\n请输入手势标签（空标签取消）: ").strip()
    finally:
        tty.setraw(sys.stdin.fileno())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="hand_gestures.json", help="gesture JSON output path")
    parser.add_argument("--robot-namespace", default="robot1")
    parser.add_argument("--side", choices=("left", "right"), default="right")
    parser.add_argument("--step", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.step <= 50:
        parser.error("--step must be in [1, 50]")

    output_file = Path(args.output).expanduser().resolve()
    pose = OPEN.copy()
    selected = 0
    step = args.step
    mode = "idle"
    gestures = {}
    global ORIGINAL_TERMIOS

    rclpy.init(args=None)
    node = HandPublisher(args.robot_namespace, args.side)
    ORIGINAL_TERMIOS = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin.fileno())
    draw(mode, pose, selected, step, gestures, output_file)
    try:
        while True:
            key = read_key()
            if key == "ESC":
                save_gestures(output_file, gestures)
                break
            if key == "r":
                mode = "editing"
                node.publish_pose(pose)
            elif key in "1234567890" and mode == "editing":
                selected = 9 if key == "0" else int(key) - 1
            elif key == "[" and mode == "editing":
                step = max(1, step - 1)
            elif key == "]" and mode == "editing":
                step = min(50, step + 1)
            elif key in ("UP", "RIGHT", "+", "=") and mode == "editing":
                pose[selected] = min(255, pose[selected] + (step if key in ("RIGHT", "+", "=") else 1))
                node.publish_pose(pose)
            elif key in ("DOWN", "LEFT", "-") and mode == "editing":
                pose[selected] = max(0, pose[selected] - (step if key in ("LEFT", "-") else 1))
                node.publish_pose(pose)
            elif key in ("\r", "\n") and mode == "editing":
                label = ask_label()
                if label:
                    gestures[label] = pose.copy()
                    save_gestures(output_file, gestures)
                    mode = "idle"
                    pose = OPEN.copy()
            draw(mode, pose, selected, step, gestures, output_file)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, ORIGINAL_TERMIOS)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        print(f"\n已保存 {len(gestures)} 个手势到: {output_file}")


if __name__ == "__main__":
    main()
