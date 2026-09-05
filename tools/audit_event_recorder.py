#!/usr/bin/env python3
"""Low-latency keyboard event recorder for a second capture auditor."""
from __future__ import annotations

import argparse
import json
import os
import sys
import termios
import time
import tty
from contextlib import suppress
from pathlib import Path
from typing import Any, Callable


DEFAULT_EVENT_KEYS = {
    "1": "approach",
    "2": "align",
    "3": "short_insert",
    "5": "stalled_or_misaligned",
    "6": "recovery_start",
    "7": "target_lost",
    "8": "retreat",
    "9": "terminal_success",
    "0": "terminal_failure",
}


def _load_event_keys() -> dict[str, str]:
    """Allow task-specific keyboard mappings through an environment override."""
    merged = dict(DEFAULT_EVENT_KEYS)
    raw = os.environ.get("TELEOP_ANNOTATION_EVENT_MAP", "")
    if not raw:
        return merged
    try:
        override = json.loads(raw)
    except (ValueError, TypeError):
        return merged
    if not isinstance(override, dict):
        return merged
    merged.update({str(key): str(value) for key, value in override.items() if isinstance(value, str)})
    return merged


EVENT_KEYS = _load_event_keys()


def load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"active": False, "status": "unavailable"}
    return value if isinstance(value, dict) else {"active": False, "status": "invalid"}


def event_for_key(
    key: str,
    state: dict[str, Any],
    *,
    auditor_id: str,
    sequence: int,
    correction_active: bool,
    ros_time_ns: int,
) -> tuple[dict[str, Any] | None, bool]:
    if not state.get("active") or not state.get("episode_id") or not state.get("run_dir"):
        return None, correction_active
    if key == "4":
        correction_active = not correction_active
        event_type = "correction_start" if correction_active else "correction_end"
    else:
        event_type = EVENT_KEYS.get(key)
    if event_type is None:
        return None, correction_active
    payload = {
        "event_type": event_type,
        "key": key,
        "auditor_id": auditor_id,
        "sequence": sequence,
        "correction_active": correction_active,
    }
    event = {
        "schema": "robot_teleop.audit-event/v0.1",
        "timestamp_ns": int(ros_time_ns),
        "timestamp_source": "capture_wall_clock",
        "monotonic_time_ns": time.monotonic_ns(),
        "wall_time_ns": time.time_ns(),
        "episode_id": str(state["episode_id"]),
        "event_type": event_type,
        "key": key,
        "auditor_id": auditor_id,
        "sequence": sequence,
        "severity": "info",
        "source": "human_auditor_keyboard",
        "payload": payload,
    }
    return event, correction_active


def append_event(run_dir: Path, event: dict[str, Any]) -> Path:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    path = artifacts / "audit_events.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return path


def print_help() -> None:
    labels = {
        "approach": "approach 接近",
        "align": "align 对齐",
        "short_insert": "short_insert 短插入/触碰",
        "press": "press 按下按钮",
        "correction_toggle": "correction 开始/结束",
        "stalled_or_misaligned": "stalled/misaligned 停滞或未对齐",
        "recovery_start": "recovery 开始恢复",
        "target_lost": "target_lost 目标丢失",
        "verify": "verify 验证",
        "retreat": "retreat 后退",
        "terminal_success": "terminal_success 任务成功",
        "terminal_failure": "terminal_failure 任务失败",
    }
    lines = [
        "\n========== AUDITOR ANNOTATION ==========",
        "数字键直接标注（无需 Enter，仅在 RECORDING 时有效）",
    ]
    for key in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
        event = EVENT_KEYS.get(key)
        if key == "4":
            lines.append("4 correction 开始/结束 toggle")
        elif event:
            lines.append(f"{key} {labels.get(event, event)}")
    lines += [
        "h help            q 退出标注窗口（不停止采集）",
        "",
    ]
    print(
        "\n".join(lines),
        flush=True,
    )


def run_keyboard(
    state_path: Path,
    auditor_id: str,
    publish: Callable[[str], None],
    ros_time_ns: Callable[[], int],
) -> int:
    if not sys.stdin.isatty():
        raise SystemExit("audit event recorder requires an interactive TTY")
    print_help()
    fd = sys.stdin.fileno()
    old_tty = termios.tcgetattr(fd)
    sequence = 0
    correction_active = False
    previous_episode: str | None = None
    try:
        tty.setcbreak(fd)
        while True:
            key = os.read(fd, 1).decode("utf-8", errors="ignore").lower()
            if key == "q":
                print("\n[AUDIT] 标注窗口已退出；采集会话未停止。", flush=True)
                return 0
            if key == "h":
                print_help()
                continue
            if key not in EVENT_KEYS and key != "4":
                continue
            state = load_state(state_path)
            episode_id = str(state.get("episode_id") or "")
            if episode_id != previous_episode:
                correction_active = False
                previous_episode = episode_id
            event, correction_active = event_for_key(
                key,
                state,
                auditor_id=auditor_id,
                sequence=sequence + 1,
                correction_active=correction_active,
                ros_time_ns=ros_time_ns(),
            )
            if event is None:
                print("\r\033[K[AUDIT] 当前没有正在录制的 episode，标注未写入。", end="", flush=True)
                continue
            sequence += 1
            encoded = json.dumps(event, sort_keys=True)
            append_event(Path(str(state["run_dir"])), event)
            publish(encoded)
            print(
                f"\r\033[K[AUDIT #{sequence}] {event['event_type']} | "
                f"episode={event['episode_id']} | timestamp_ns={event['timestamp_ns']}",
                end="",
                flush=True,
            )
    finally:
        with suppress(termios.error):
            termios.tcsetattr(fd, termios.TCSADRAIN, old_tty)
        print(flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--auditor-id", default="auditor_01")
    parser.add_argument("--topic", default="/teleop/events")
    args = parser.parse_args()

    import rclpy
    from std_msgs.msg import String

    rclpy.init()
    node = rclpy.create_node("teleop_audit_event_recorder")
    publisher = node.create_publisher(String, args.topic, 10)

    def publish(payload: str) -> None:
        message = String()
        message.data = payload
        publisher.publish(message)

    try:
        return run_keyboard(
            args.state_file,
            args.auditor_id,
            publish,
            lambda: node.get_clock().now().nanoseconds,
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
