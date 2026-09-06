#!/usr/bin/env python3
"""Build timestamped multi-camera temporal windows for VLM auditing/training."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stamp(row: dict[str, Any]) -> int:
    value = row.get("timestamp_ns", row.get("header_stamp_ns"))
    if not isinstance(value, int):
        raise ValueError("all frame and event rows require integer timestamp_ns")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, required=True, help="timestamped keyframe index JSONL")
    parser.add_argument("--events", type=Path, help="reviewed human event JSONL")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--window-ms", type=int, default=4000)
    parser.add_argument("--stride-ms", type=int, default=500)
    parser.add_argument("--frame-interval-ms", type=int, default=200)
    parser.add_argument("--max-frames-per-camera", type=int, default=24)
    parser.add_argument("--causal", action="store_true", help="window ends at anchor and never includes future frames")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite output: {args.output}")
    if min(args.window_ms, args.stride_ms, args.frame_interval_ms, args.max_frames_per_camera) < 1:
        raise SystemExit("window, stride, frame interval and frame limit must be positive")
    frames = sorted(load(args.frames), key=stamp)
    missing_refs = [row.get("reference") for row in frames if not isinstance(row.get("reference"), str) or not Path(row["reference"]).is_file()]
    if missing_refs:
        raise SystemExit(f"frame index contains {len(missing_refs)} missing/unreadable references; re-extract keyframes from the immutable rosbag")
    if not frames:
        raise SystemExit("frame index is empty")
    events = sorted(load(args.events), key=stamp) if args.events else []
    start = stamp(frames[0])
    end = stamp(frames[-1])
    window_ns = args.window_ms * 1_000_000
    stride_ns = args.stride_ms * 1_000_000
    interval_ns = args.frame_interval_ms * 1_000_000
    cameras = sorted({str(row.get("camera_id", "unknown")) for row in frames})
    windows: list[dict[str, Any]] = []
    anchor = start + (window_ns if args.causal else 0)
    while anchor <= end:
        left = anchor - window_ns
        right = anchor if args.causal else anchor + window_ns
        selected: dict[str, list[dict[str, Any]]] = {}
        for camera in cameras:
            candidates = [row for row in frames if str(row.get("camera_id", "unknown")) == camera and left <= stamp(row) <= right]
            sampled: list[dict[str, Any]] = []
            last = None
            for row in candidates:
                if last is None or stamp(row) - last >= interval_ns:
                    sampled.append({"timestamp_ns": stamp(row), "reference": row.get("reference"), "camera_id": camera})
                    last = stamp(row)
            selected[camera] = sampled[-args.max_frames_per_camera:]
        event_rows = [event for event in events if left <= stamp(event) <= right]
        correction_active = False
        # Carry state from events before the window boundary; otherwise a
        # long correction segment would appear inactive in later windows.
        for event in events:
            if stamp(event) > right:
                break
            if event.get("event_type") == "correction_start":
                correction_active = True
            elif event.get("event_type") == "correction_end":
                correction_active = False
        starts = [stamp(event) for event in event_rows if event.get("event_type") == "correction_start"]
        ends = [stamp(event) for event in event_rows if event.get("event_type") == "correction_end"]
        windows.append({
            "schema": "robot_teleop.vlm-temporal-window/v0.1",
            "anchor_timestamp_ns": anchor,
            "window_start_ns": left,
            "window_end_ns": right,
            "causal": args.causal,
            "camera_ids": cameras,
            "frames": selected,
            "events": event_rows,
            "labels": {
                "correction_active": correction_active,
                "correction_start": bool(starts and (not args.causal or starts[-1] <= anchor)),
                "correction_end": bool(ends and (not args.causal or ends[-1] <= anchor)),
                "human_event_count": len(event_rows),
            },
            "attention": {
                "policy": "temporal_self_attention_over_ordered_frames",
                "causal": args.causal,
                "future_frames_included": not args.causal,
                "anchor_timestamp_ns": anchor,
            },
        })
        anchor += stride_ns
    if not windows:
        raise SystemExit("no temporal windows generated")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in windows), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "windows": len(windows), "cameras": cameras, "causal": args.causal}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
