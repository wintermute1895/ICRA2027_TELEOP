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
from tkinter import ttk

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
        self.gesture_ids = sorted(gestures)
        self.selected = self.gesture_ids[0]
        self.closed = False
        self.value_labels: list[tk.Label] = []
        self.value_bars: list[ttk.Progressbar] = []
        self.gesture_buttons: dict[int, tk.Button] = {}
        self.maximum = 255.0 if hand.upper() == "L10" else 100.0

        root.title(f"DexCatch {hand} Gesture Player")
        root.geometry("960x620")
        root.minsize(780, 500)
        root.configure(bg="#101820")
        root.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Value.Horizontal.TProgressbar", troughcolor="#263442", background="#37b7a5", bordercolor="#263442", lightcolor="#37b7a5", darkcolor="#37b7a5")
        style.configure("Execute.TButton", font=("Arial", 13, "bold"), foreground="white", background="#087f8c", padding=(18, 10))
        style.map("Execute.TButton", background=[("active", "#0b9aaa"), ("disabled", "#425563")])

        self._build_header()
        body = tk.Frame(root, bg="#101820")
        body.pack(fill="both", expand=True, padx=22, pady=(0, 16))
        self._build_gesture_list(body)
        self._build_detail_panel(body)
        self._build_footer()

        # bind_all also catches keys when focus is on the button/labels
        root.bind_all("<Key>", self.on_key)
        root.bind_all("<Return>", self.execute)
        root.bind_all("<KP_Enter>", self.execute)
        root.bind_all("<Up>", lambda _event: self.select_relative(-1))
        root.bind_all("<Down>", lambda _event: self.select_relative(1))
        root.bind_all("<Escape>", self.close)
        self.render()
        root.after(100, root.focus_force)

    def _build_header(self):
        header = tk.Frame(self.root, bg="#162431")
        header.pack(fill="x", padx=22, pady=(20, 14))
        left = tk.Frame(header, bg="#162431"); left.pack(side="left", padx=18, pady=14)
        tk.Label(left, text=f"DexCatch  ·  {self.hand}", font=("Arial", 22, "bold"), fg="#f3f7fa", bg="#162431").pack(anchor="w")
        tk.Label(left, text="手势执行面板", font=("Arial", 11), fg="#93aabd", bg="#162431").pack(anchor="w", pady=(3, 0))
        self.connection = tk.Label(header, text="● 已连接   ·   选择不会发送动作", font=("Arial", 11, "bold"), fg="#55d6be", bg="#162431")
        self.connection.pack(side="right", padx=18, pady=14)

    def _build_gesture_list(self, parent):
        panel = tk.Frame(parent, bg="#162431", width=235)
        panel.pack(side="left", fill="y", padx=(0, 14)); panel.pack_propagate(False)
        tk.Label(panel, text="已录制手势", font=("Arial", 13, "bold"), fg="#f3f7fa", bg="#162431").pack(anchor="w", padx=18, pady=(18, 2))
        tk.Label(panel, text="数字键 / ↑↓ 选择", font=("Arial", 10), fg="#839aaa", bg="#162431").pack(anchor="w", padx=18, pady=(0, 14))
        for number in self.gesture_ids:
            button = tk.Button(panel, text=f"  手势 {number}", anchor="w", command=lambda n=number: self.select(n),
                               font=("Arial", 12, "bold"), fg="#dce8ef", bg="#213442", activeforeground="white",
                               activebackground="#087f8c", relief="flat", bd=0, padx=10, pady=10, cursor="hand2")
            button.pack(fill="x", padx=12, pady=3)
            self.gesture_buttons[number] = button

    def _build_detail_panel(self, parent):
        panel = tk.Frame(parent, bg="#162431")
        panel.pack(side="left", fill="both", expand=True)
        top = tk.Frame(panel, bg="#162431"); top.pack(fill="x", padx=24, pady=(20, 12))
        self.selection = tk.Label(top, font=("Arial", 19, "bold"), fg="#f3f7fa", bg="#162431")
        self.selection.pack(side="left")
        tk.Label(top, text="输出范围  0 – %.0f" % self.maximum, font=("Arial", 10), fg="#839aaa", bg="#162431").pack(side="right", pady=5)
        self.rows = tk.Frame(panel, bg="#162431"); self.rows.pack(fill="both", expand=True, padx=24, pady=4)
        for index in range(len(self.gestures[self.selected])):
            row = tk.Frame(self.rows, bg="#213442"); row.pack(fill="x", pady=4)
            tk.Label(row, text=f"J{index + 1:02d}", width=6, anchor="w", font=("Consolas", 12, "bold"), fg="#9fb4c2", bg="#213442").pack(side="left", padx=(12, 8), pady=10)
            bar = ttk.Progressbar(row, style="Value.Horizontal.TProgressbar", maximum=self.maximum)
            bar.pack(side="left", fill="x", expand=True, padx=4)
            value = tk.Label(row, width=8, anchor="e", font=("Consolas", 13, "bold"), fg="#f3f7fa", bg="#213442")
            value.pack(side="right", padx=(8, 14))
            self.value_bars.append(bar); self.value_labels.append(value)

    def _build_footer(self):
        footer = tk.Frame(self.root, bg="#101820")
        footer.pack(fill="x", padx=22, pady=(0, 18))
        self.status = tk.Label(footer, text="就绪：选择手势后按 Enter 执行", anchor="w", font=("Arial", 11), fg="#f2c879", bg="#101820")
        self.status.pack(side="left", fill="x", expand=True)
        tk.Button(footer, text="退出  Esc", command=self.close, font=("Arial", 11), fg="#b6c5cf", bg="#162431", activebackground="#263442", relief="flat", padx=14, pady=8).pack(side="right", padx=(8, 0))
        self.execute_button = ttk.Button(footer, text="执行当前手势  Enter", command=self.execute, style="Execute.TButton")
        self.execute_button.pack(side="right")

    def render(self, message: str | None = None):
        values = self.gestures[self.selected]
        self.selection.config(text=f"手势 {self.selected}   ·   {len(values)} 个关节")
        for index, value in enumerate(values):
            self.value_bars[index]["value"] = value
            self.value_labels[index].config(text=f"{value:.1f}")
        for number, button in self.gesture_buttons.items():
            selected = number == self.selected
            button.config(bg="#087f8c" if selected else "#213442", fg="white" if selected else "#dce8ef")
        if message: self.status.config(text=message)

    def select(self, number: int):
        if number in self.gestures:
            self.selected = number
            self.render(f"已选择手势 {number} · 不会发送动作 · 按 Enter 执行")

    def select_relative(self, offset: int):
        index = self.gesture_ids.index(self.selected)
        self.select(self.gesture_ids[(index + offset) % len(self.gesture_ids)])

    def on_key(self, event):
        if event.char.isdigit():
            number = int(event.char)
            if number in self.gestures:
                self.select(number)
            else:
                self.render(f"手势 {number} 不存在 · 可用编号：{self.gesture_ids}")

    def execute(self, _event=None):
        if self.closed: return
        try:
            self.execute_button.config(state="disabled")
            self.status.config(text=f"正在发送手势 {self.selected} …")
            self.root.update_idletasks()
            self.device.write(self.gestures[self.selected])
            self.render(f"✓ 已执行手势 {self.selected} · {len(self.gestures[self.selected])} 个关节")
        except Exception as exc:
            self.status.config(text=f"✕ 执行失败：{exc}", fg="#ff8c8c")
            messagebox.showerror("执行失败", str(exc), parent=self.root)
        finally:
            if not self.closed: self.execute_button.config(state="normal")

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
