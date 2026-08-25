"""Interactive recorder. Run with --help; hardware is never opened by import."""
from __future__ import annotations
import argparse, sys, shutil, json
from pathlib import Path
from .adapters import create_adapter
from .gestures import GestureFile, GestureSet

def _key_stream():
    if sys.platform == "win32":
        import msvcrt
        while True:
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"): key = {"H":"up", "P":"down", "K":"left", "M":"right"}.get(msvcrt.getwch(), "")
            yield key
    else:
        import tty, termios
        fd=sys.stdin.fileno(); old=termios.tcgetattr(fd); tty.setcbreak(fd)
        try:
            while True:
                c=sys.stdin.read(1)
                if c=="\x1b":
                    seq=sys.stdin.read(2); yield {"[A":"up","[B":"down","[C":"right","[D":"left"}.get(seq, "")
                else: yield c
        finally: termios.tcsetattr(fd, termios.TCSADRAIN, old)

def _draw(hand, values, selected, selected_joints, saved_count, message=""):
    width = shutil.get_terminal_size((100, 30)).columns
    lines = [f"Hand gesture recorder | {hand.name} | range {hand.minimum:g}..{hand.maximum:g}",
             "=" * min(width, 78), "Current joint values (selected joint is marked >):"]
    for start in range(0, len(values), 5):
        row = []
        for i in range(start, min(start + 5, len(values))):
            marker = "+" if i in selected_joints else (">" if i == selected else " ")
            row.append(f"{marker}J{i + 1:02d}: {values[i]:7.2f}")
        lines.append("   ".join(row))
    selected_text = ",".join(f"J{i + 1}" for i in sorted(selected_joints)) or "none"
    lines += ["", f"Cursor: J{selected + 1}    Multi-selected: {selected_text}    Saved gestures: {saved_count}",
              "Controls: number=cursor | space=toggle | a=all | x=clear | arrows=adjust | r=refresh | s=save | q=quit"]
    if message: lines.append(f"Status: {message}")
    sys.stdout.write("\x1b[2J\x1b[H" + "\n".join(lines) + "\n"); sys.stdout.flush()

def main(argv=None):
    p=argparse.ArgumentParser(description="Record numbered L10/O6 hand poses")
    p.add_argument("--hand", choices=["L10","O6"], required=True); p.add_argument("--side", default="left", choices=["left","right"])
    p.add_argument("--can", default="can0"); p.add_argument("--output", default="gestures"); p.add_argument("--step", type=float, default=1.0); p.add_argument("--simulate", action="store_true")
    p.add_argument("--overwrite", action="store_true", help="overwrite gesture slots 0, 1, and 2 in order")
    a=p.parse_args(argv); device=create_adapter(a.hand,a.side,a.can,a.simulate); values=device.read(); selected=0; selected_joints={0}
    existing = Path(a.output) / f"{a.hand.lower()}_gestures.json"
    if existing.exists():
        try:
            saved = GestureFile.load_json(existing)
            if saved.hand.upper() != a.hand.upper():
                saved = GestureSet(a.hand)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            saved = GestureSet(a.hand)
    else:
        saved = GestureSet(a.hand)
    number = 0 if a.overwrite else max(saved.gestures, default=-1) + 1
    status = (
        "Ready; overwrite mode: adjust pose, then press s to replace gesture "
        f"{number}"
        if a.overwrite else
        (f"Ready; next gesture number is {number}" if number else "Ready; next gesture number is 0")
    )
    _draw(device, values, selected, selected_joints, len(saved.gestures), status)
    try:
        for key in _key_stream():
            if key in ("q","Q"): break
            if key in ("s","S"):
                if a.overwrite and number > 2:
                    _draw(device, values, selected, selected_joints, len(saved.gestures), "Gestures 0, 1, and 2 are complete; press q to exit")
                    continue
                saved.add(number, values); number += 1
                message = f"Overwrote gesture {number - 1}" if a.overwrite else f"Saved gesture {number - 1}"
                if a.overwrite and number <= 2:
                    message += f"; next is {number}"
                elif a.overwrite:
                    message += "; 0, 1, and 2 complete"
                _draw(device, values, selected, selected_joints, len(saved.gestures), message); continue
            if key in ("a", "A"):
                selected_joints = set(range(len(values)))
                _draw(device, values, selected, selected_joints, len(saved.gestures), "All joints selected"); continue
            if key in ("x", "X"):
                selected_joints.clear()
                _draw(device, values, selected, selected_joints, len(saved.gestures), "Selection cleared"); continue
            if key == " ":
                if selected in selected_joints: selected_joints.remove(selected)
                else: selected_joints.add(selected)
                _draw(device, values, selected, selected_joints, len(saved.gestures), "Selection updated"); continue
            if key in ("r", "R"):
                try:
                    actual = device.read()
                    if len(actual) == len(values):
                        values = [float(v) for v in actual]
                        _draw(device, values, selected, selected_joints, len(saved.gestures), "Read actual hand state")
                    else:
                        _draw(device, values, selected, selected_joints, len(saved.gestures), "Invalid state length")
                except Exception as exc:
                    _draw(device, values, selected, selected_joints, len(saved.gestures), f"Read failed: {exc}")
                continue
            if key in ("up","down","left","right"):
                delta=a.step if key in ("up","right") else -a.step
                targets = selected_joints or {selected}
                for joint in targets:
                    values[joint] = max(device.minimum, min(device.maximum, values[joint] + delta))
                device.write(values)
                _draw(device, values, selected, selected_joints, len(saved.gestures), f"Adjusted {len(targets)} joint(s)")
            elif key.isdigit():
                joint = 9 if key == "0" and len(values) == 10 else int(key) - 1
                if 0 <= joint < len(values): selected=joint; _draw(device, values, selected, selected_joints, len(saved.gestures), f"Cursor J{selected + 1}")
    finally:
        device.close()
    if saved.gestures: print("\nWritten:", *saved.export(a.output))

if __name__ == "__main__": main()
