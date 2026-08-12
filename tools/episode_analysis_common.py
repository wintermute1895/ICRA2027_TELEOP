"""Small, dependency-light helpers for offline canonical episode analysis."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSON at {path}:{line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise SystemExit(f"record at {path}:{line_number} is not an object")
        records.append(record)
    if not records:
        raise SystemExit(f"episode is empty: {path}")
    return records


def finite_vector(value: Any, length: int | None = None) -> list[float] | None:
    if not isinstance(value, list) or (length is not None and len(value) != length):
        return None
    try:
        result = [float(item) for item in value]
    except (TypeError, ValueError):
        return None
    return result if all(math.isfinite(item) for item in result) else None


def percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return None
    index = (len(ordered) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def scalar_summary(values: Iterable[float]) -> dict[str, float | int | None]:
    numbers = [float(value) for value in values if math.isfinite(float(value))]
    if not numbers:
        return {"count": 0, "mean": None, "rms": None, "p50": None, "p95": None, "minimum": None, "maximum": None}
    return {
        "count": len(numbers),
        "mean": sum(numbers) / len(numbers),
        "rms": math.sqrt(sum(value * value for value in numbers) / len(numbers)),
        "p50": percentile(numbers, 0.5),
        "p95": percentile(numbers, 0.95),
        "minimum": min(numbers),
        "maximum": max(numbers),
    }


def max_abs(vector: list[float] | None) -> float | None:
    return None if vector is None else max((abs(value) for value in vector), default=0.0)
