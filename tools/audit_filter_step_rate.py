#!/usr/bin/env python3
"""Measure filter-training step intervals from timestamped JSONL views."""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def timestamp_ns(row: dict[str, Any]) -> int | None:
    value = row.get("timestamp_ns", row.get("header_stamp_ns"))
    return int(value) if isinstance(value, int) else None


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be in [0, 1]")
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_rows(
    rows: Iterable[dict[str, Any]],
    *,
    history_length: int = 16,
    horizon: int = 8,
    runtime_hz: float | None = None,
) -> dict[str, Any]:
    if history_length < 1 or horizon < 1:
        raise ValueError("history_length and horizon must be positive")
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        stamp = timestamp_ns(row)
        if stamp is None:
            continue
        episode_id = str(row.get("episode_id") or "unscoped")
        grouped[episode_id].append(stamp)
    episodes: list[dict[str, Any]] = []
    all_differences_ms: list[float] = []
    for episode_id, stamps in sorted(grouped.items()):
        ordered = sorted(set(stamps))
        differences_ms = [
            (current - previous) / 1_000_000.0
            for previous, current in zip(ordered, ordered[1:])
            if current > previous
        ]
        if not differences_ms:
            continue
        all_differences_ms.extend(differences_ms)
        median_dt_ms = percentile(differences_ms, 0.5)
        episodes.append({
            "episode_id": episode_id,
            "rows": len(stamps),
            "unique_timestamps": len(ordered),
            "intervals": len(differences_ms),
            "median_dt_ms": median_dt_ms,
            "median_hz": 1000.0 / median_dt_ms,
            "p05_dt_ms": percentile(differences_ms, 0.05),
            "p95_dt_ms": percentile(differences_ms, 0.95),
        })
    if not all_differences_ms:
        raise ValueError("no positive timestamp intervals found")
    median_dt_ms = percentile(all_differences_ms, 0.5)
    median_hz = 1000.0 / median_dt_ms
    result: dict[str, Any] = {
        "schema": "robot_teleop.filter-step-rate-audit/v0.1",
        "rows_with_timestamps": sum(len(values) for values in grouped.values()),
        "episodes": episodes,
        "median_dt_ms": median_dt_ms,
        "mean_dt_ms": sum(all_differences_ms) / len(all_differences_ms),
        "p05_dt_ms": percentile(all_differences_ms, 0.05),
        "p95_dt_ms": percentile(all_differences_ms, 0.95),
        "median_hz": median_hz,
        "history_seconds_at_median": history_length * median_dt_ms / 1000.0,
        "horizon_seconds_at_median": horizon * median_dt_ms / 1000.0,
    }
    if runtime_hz is not None:
        if runtime_hz <= 0.0:
            raise ValueError("runtime_hz must be positive")
        runtime_dt_ms = 1000.0 / runtime_hz
        result.update({
            "runtime_hz": runtime_hz,
            "runtime_dt_ms": runtime_dt_ms,
            "runtime_history_seconds": history_length * runtime_dt_ms / 1000.0,
            "runtime_horizon_seconds": horizon * runtime_dt_ms / 1000.0,
            "time_scale_ratio": runtime_dt_ms / median_dt_ms,
        })
    return result


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, action="append", required=True)
    parser.add_argument("--history-length", type=int, default=16)
    parser.add_argument("--horizon", type=int, default=8)
    parser.add_argument("--runtime-hz", type=float)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for path in args.episode:
        for row in read_jsonl(path):
            row.setdefault("episode_id", path.stem)
            rows.append(row)
    result = summarize_rows(
        rows,
        history_length=args.history_length,
        horizon=args.horizon,
        runtime_hz=args.runtime_hz,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
