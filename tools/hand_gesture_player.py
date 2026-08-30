"""Small GUI player for recorded L10 gestures.

Usage::
    python -m tools.hand_gesture_player --hand L10 --side right --can can0
    python -m tools.hand_gesture_player --hand L10 --simulate

Click the window to focus it, press 0/1/2 to select a gesture, then Enter to
send the complete ten-joint pose. Selection never sends a hardware command.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from tools.hand_gesture_recorder.adapters import create_adapter


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
    def __init__(self, root: tk.Tk, gestures: dict[int, list[float]], device, hand: str):
        self.root, self.gestures, self.device, self.hand = root, gestures, device, hand
        self.selected = min(gestures)
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
            self.render(f"已执行手势 {self.selected}（{len(self.gestures[self.selected])} 个自由度）")
        except Exception as exc:
            self.status.config(text=f"执行失败：{exc}")
            messagebox.showerror("执行失败", str(exc), parent=self.root)

    def close(self, _event=None):
        if self.closed: return
        self.closed = True
        try: self.device.close()
        finally: self.root.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Display and execute recorded hand gestures")
    parser.add_argument("--hand", choices=["L10", "O6"], required=True)
    parser.add_argument("--side", choices=["left", "right"], default="left")
    parser.add_argument("--can", default="can0")
    parser.add_argument("--output", default="gestures")
    parser.add_argument("--simulate", action="store_true", help="do not connect hardware")
    args = parser.parse_args(argv)
    gestures = load_gestures(args.output, args.hand)
    device = create_adapter(args.hand, args.side, args.can, args.simulate)
    root = tk.Tk()
    GesturePlayer(root, gestures, device, args.hand)
    root.mainloop()


if __name__ == "__main__":
    main()
