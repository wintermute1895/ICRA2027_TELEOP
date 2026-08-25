#!/usr/bin/env python3
"""Graphical L10/O6 gesture player backed by the lbot_driver ROS2 topic."""

from __future__ import annotations

import argparse
import threading
import tkinter as tk

import rclpy

from ros_hand_publisher import DirectL10Can, HandPublisher, load_gestures


def spin_node(node: HandPublisher) -> None:
    try:
        rclpy.spin(node)
    except Exception:
        # Closing the window shuts down the context while the spin thread may
        # still be waiting on its executor.
        if rclpy.ok():
            raise


class RosGesturePlayer:
    def __init__(self, root: tk.Tk, node: HandPublisher, gestures: dict[int, list[int]], hand: str):
        self.root = root
        self.node = node
        self.gestures = gestures
        self.hand = hand
        self.selected = min(gestures)
        self.closed = False

        root.title(f"{hand} 手部 ROS 手势播放器")
        root.geometry("820x520")
        root.minsize(680, 420)
        root.configure(bg="#17202a")
        tk.Label(
            root, text=f"{hand} 手部手势播放器", font=("Arial", 22, "bold"),
            fg="white", bg="#17202a"
        ).pack(pady=(18, 4))
        tk.Label(
            root, text="选择手势后点击发送，或按数字键选择、Enter 发送，Esc 退出",
            font=("Arial", 12), fg="#b8c7d9", bg="#17202a"
        ).pack()

        self.selection = tk.Label(
            root, font=("Arial", 18, "bold"), fg="#5dade2", bg="#17202a"
        )
        self.selection.pack(pady=10)
        self.buttons = tk.Frame(root, bg="#17202a")
        self.buttons.pack(pady=(0, 8))
        for number in sorted(gestures):
            tk.Button(
                self.buttons, text=f"手势 {number}", command=lambda n=number: self.choose(n),
                font=("Arial", 12, "bold"), fg="white", bg="#273746",
                activebackground="#2980b9", padx=14, pady=5
            ).pack(side="left", padx=5)
        tk.Button(
            root, text="发送当前手势 (Enter)", command=self.execute,
            font=("Arial", 14, "bold"), fg="white", bg="#1f618d",
            activebackground="#2980b9", padx=20, pady=7
        ).pack(pady=(0, 10))

        self.rows = tk.Frame(root, bg="#17202a")
        self.rows.pack(fill="both", expand=True, padx=28)
        self.status = tk.Label(
            root, text="发布器已启动：当前姿态会持续写入 ROS 话题",
            font=("Arial", 12), fg="#f7dc6f", bg="#17202a"
        )
        self.status.pack(pady=12)
        root.bind_all("<Key>", self.on_key)
        root.bind_all("<Return>", self.execute)
        root.bind_all("<KP_Enter>", self.execute)
        root.bind_all("<Escape>", self.close)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.render()
        root.after(100, root.focus_force)

    def render(self, message: str | None = None) -> None:
        for child in self.rows.winfo_children():
            child.destroy()
        self.selection.config(text=f"待发送手势：{self.selected}")
        values = self.gestures[self.selected]
        for start in range(0, len(values), 5):
            row = tk.Frame(self.rows, bg="#17202a")
            row.pack(fill="x", pady=5)
            for index in range(start, min(start + 5, len(values))):
                tk.Label(
                    row, text=f"J{index + 1:02d}\n{values[index]}", width=12, height=2,
                    font=("Consolas", 14), fg="white", bg="#273746"
                ).pack(side="left", padx=4, expand=True, fill="x")
        if message:
            self.status.config(text=message)

    def choose(self, number: int) -> None:
        self.selected = number
        self.render(f"已选择手势 {number}，点击发送或按 Enter")

    def on_key(self, event: tk.Event) -> None:
        if event.char.isdigit() and int(event.char) in self.gestures:
            self.choose(int(event.char))

    def execute(self, _event=None) -> None:
        self.node.selected = self.selected
        self.render(f"已发送手势 {self.selected}，正在持续发布")

    def close(self, _event=None) -> None:
        if self.closed:
            return
        self.closed = True
        self.node.stop_requested = True
        if rclpy.ok():
            rclpy.shutdown()
        self.root.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--side", choices=("left", "right"), default="right")
    parser.add_argument("--robot-namespace", default="robot1")
    parser.add_argument("--topic", default=None)
    parser.add_argument("--can", default="can0")
    parser.add_argument("--hand", choices=("L10", "O6"), default="O6")
    parser.add_argument("--direct-can", action="store_true")
    parser.add_argument("--output", default="gestures")
    parser.add_argument("--rate", type=float, default=10.0)
    args = parser.parse_args(argv)
    if args.rate <= 0:
        parser.error("--rate must be greater than zero")

    gestures = load_gestures(args.output, args.hand)
    namespace = args.robot_namespace.strip("/")
    joint_suffix = "l10" if args.hand == "L10" else "l6"
    topic = args.topic or f"/{namespace}/{args.side}_hand/set_{joint_suffix}_joint"
    if args.direct_can and args.hand != "L10":
        parser.error("--direct-can currently supports L10 only; publish O6 through lbot_driver")
    hardware = DirectL10Can(args.side, args.can) if args.direct_can else None
    rclpy.init()
    node = HandPublisher(topic, gestures, args.rate, hardware)
    spin_thread = threading.Thread(target=spin_node, args=(node,), daemon=True)
    spin_thread.start()
    root = tk.Tk()
    RosGesturePlayer(root, node, gestures, args.hand)
    root.mainloop()
    if hardware is not None:
        hardware.close()
    node.destroy_node()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
