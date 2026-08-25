"""Small GUI player for recorded O6 gestures.

Usage::
    python hand_gesture_player.py --hand O6 --side right --can can0
    python hand_gesture_player.py --hand O6 --simulate

Click the window to focus it, press 0/1/2 to select a gesture, then Enter to
send the complete six-joint pose. Selection never sends a hardware command.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox

from hand_gesture_recorder.adapters import create_adapter


class RosMirror:
    """Continuously mirror the active direct-CAN pose into a ROS bag topic."""

    def __init__(self, topic: str, rate: float, pose_supplier):
        import rclpy
        from rclpy.node import Node
        from std_msgs.msg import UInt8MultiArray

        self._rclpy = rclpy
        self._pose_supplier = pose_supplier

        class MirrorNode(Node):
            def __init__(self):
                super().__init__("o6_hand_gesture_player")
                self.pose_supplier = pose_supplier
                self.publisher = self.create_publisher(UInt8MultiArray, topic, 10)
                self.timer = self.create_timer(1.0 / rate, self.publish_pose)

            def publish_pose(self):
                # O6 angles are 0..100; the lbot L6 ROS API accepts 0..255 bytes.
                values = self.pose_supplier()
                message = UInt8MultiArray()
                message.data = [
                    max(0, min(255, int(round(float(value) * 255.0 / 100.0))))
                    for value in values
                ]
                self.publisher.publish(message)

        rclpy.init()
        self._node = MirrorNode()
        self._thread = threading.Thread(
            target=self._spin, name="o6-ros-mirror", daemon=True
        )
        self._thread.start()

    def _spin(self):
        try:
            self._rclpy.spin(self._node)
        except Exception:
            if self._rclpy.ok():
                raise

    def close(self):
        if self._rclpy.ok():
            self._node.destroy_node()
            self._rclpy.shutdown()
        self._thread.join(timeout=2.0)


def load_gestures(output: str, hand: str) -> dict[int, list[float]]:
    path = Path(output) / f"{hand.lower()}_gestures.json"
    if not path.exists():
        raise FileNotFoundError(f"gesture file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if str(data.get("hand", "")).upper() != hand.upper():
        raise ValueError(f"gesture file is for {data.get('hand')!r}, not {hand}")
    result = {int(k): [float(v) for v in values] for k, values in data.get("gestures", {}).items()}
    expected = 10 if hand.upper() == "L10" else 6
    if not result or any(len(values) != expected for values in result.values()):
        raise ValueError(f"all gestures must contain exactly {expected} joints")
    return result


class GesturePlayer:
    def __init__(
        self,
        root: tk.Tk,
        gestures: dict[int, list[float]],
        device,
        hand: str,
        ros_mirror: RosMirror | None = None,
    ):
        self.root, self.gestures, self.device, self.hand = root, gestures, device, hand
        self.selected = min(gestures)
        self.active = self.selected
        self.ros_mirror = ros_mirror
        self.closed = False
        root.title(f"DexCatch {hand} Gesture Player")
        root.geometry("760x460")
        root.minsize(600, 360)
        root.configure(bg="#17202a")
        self.title = tk.Label(root, text=f"{hand} 手势执行器", font=("Arial", 22, "bold"), fg="white", bg="#17202a")
        self.title.pack(pady=(18, 4))
        tk.Label(root, text="点击窗口聚焦 · 数字键选择 · Enter 执行 · Esc 退出", font=("Arial", 12), fg="#b8c7d9", bg="#17202a").pack()
        self.selection = tk.Label(root, font=("Arial", 18, "bold"), fg="#5dade2", bg="#17202a")
        self.selection.pack(pady=10)
        self.execute_button = tk.Button(root, text="执行当前手势 (Enter)", command=self.execute,
                                        font=("Arial", 14, "bold"), fg="white", bg="#1f618d",
                                        activebackground="#2980b9", relief="raised", padx=20, pady=6)
        self.execute_button.pack(pady=(0, 10))
        self.rows = tk.Frame(root, bg="#17202a"); self.rows.pack(fill="both", expand=True, padx=28)
        self.status = tk.Label(root, text="就绪：选择手势后按 Enter 执行", font=("Arial", 12), fg="#f7dc6f", bg="#17202a")
        self.status.pack(pady=12)
        # bind_all also catches keys when focus is on the button/labels
        root.bind_all("<Key>", self.on_key)
        root.bind_all("<Return>", self.execute)
        root.bind_all("<KP_Enter>", self.execute)
        root.bind_all("<Escape>", self.close)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.render()
        root.after(100, root.focus_force)

    def render(self, message: str | None = None):
        for child in self.rows.winfo_children(): child.destroy()
        self.selection.config(text=f"当前选择：手势 {self.selected}    （共 {len(self.gestures)} 个手势）")
        values = self.gestures[self.selected]
        for start in range(0, len(values), 5):
            row = tk.Frame(self.rows, bg="#17202a"); row.pack(fill="x", pady=5)
            for i in range(start, min(start + 5, len(values))):
                tk.Label(row, text=f"J{i + 1:02d}\n{values[i]:.1f}", width=12, height=2,
                         font=("Consolas", 14), fg="white", bg="#273746").pack(side="left", padx=4, expand=True, fill="x")
        if message: self.status.config(text=message)

    def on_key(self, event):
        if event.char.isdigit():
            number = int(event.char)
            if number in self.gestures:
                self.selected = number; self.render(f"已选择手势 {number}，按 Enter 执行")
            else:
                self.render(f"手势 {number} 不存在；可用编号：{sorted(self.gestures)}")

    def execute(self, _event=None):
        try:
            self.status.config(text=f"正在发送手势 {self.selected} ...")
            self.root.update_idletasks()
            self.device.write(self.gestures[self.selected])
            self.active = self.selected
            self.render(f"已执行手势 {self.selected}（{len(self.gestures[self.selected])} 个自由度）")
        except Exception as exc:
            self.status.config(text=f"执行失败：{exc}")
            messagebox.showerror("执行失败", str(exc), parent=self.root)

    def close(self, _event=None):
        if self.closed: return
        self.closed = True
        try:
            if self.ros_mirror is not None:
                self.ros_mirror.close()
            self.device.close()
        finally: self.root.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Display and execute recorded hand gestures")
    parser.add_argument(
        "--hand",
        choices=["O6", "L10"],
        default="O6",
        help="hand model (default: O6; use L10 only for the legacy 10-joint hand)",
    )
    parser.add_argument("--side", choices=["left", "right"], default="left")
    parser.add_argument("--can", default="can0")
    parser.add_argument("--output", default="gestures")
    parser.add_argument("--simulate", action="store_true", help="do not connect hardware")
    parser.add_argument(
        "--ros-mirror",
        action="store_true",
        help="also publish the active O6 pose continuously for rosbag recording",
    )
    parser.add_argument("--ros-topic", default=None, help="ROS mirror topic")
    parser.add_argument("--ros-rate", type=float, default=10.0)
    args = parser.parse_args(argv)
    if args.ros_rate <= 0:
        parser.error("--ros-rate must be greater than zero")
    if args.ros_mirror and args.hand != "O6":
        parser.error("--ros-mirror currently supports O6 only")
    gestures = load_gestures(args.output, args.hand)
    device = create_adapter(args.hand, args.side, args.can, args.simulate)
    root = tk.Tk()
    namespace = "robot1"
    topic = args.ros_topic or f"/{namespace}/{args.side}_hand/set_l6_joint"
    player = GesturePlayer(root, gestures, device, args.hand)
    if args.ros_mirror:
        player.ros_mirror = RosMirror(
            topic, args.ros_rate, lambda: player.gestures[player.active]
        )
    root.mainloop()


if __name__ == "__main__":
    main()
