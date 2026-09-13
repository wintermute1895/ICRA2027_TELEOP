"""Small, model-independent Filter experiment loop primitives."""
from __future__ import annotations
import numpy as np

def bounded_gain(mode: str, *, model_gain: float | None, alpha: float, alpha_max: float,
                 fallback_alpha: float = 0.0) -> float:
    if mode == "zero": value = 0.0
    elif mode == "fixed": value = alpha
    elif mode == "learned": value = fallback_alpha if model_gain is None else model_gain
    else: raise ValueError(f"unknown authority mode: {mode}")
    if not np.isfinite(value): raise ValueError("gain must be finite")
    return float(np.clip(value, 0.0, alpha_max))

def rate_limit_gain(value: float, previous: float | None, rate: float, dt_s: float) -> float:
    if previous is None or rate <= 0: return value
    return float(np.clip(value, previous - rate * dt_s, previous + rate * dt_s))

def compose(raw: np.ndarray, candidate: np.ndarray, gain: float) -> np.ndarray:
    raw, candidate = np.asarray(raw, dtype=np.float32), np.asarray(candidate, dtype=np.float32)
    if raw.shape != candidate.shape or raw.ndim != 1 or not np.isfinite(raw).all() or not np.isfinite(candidate).all():
        raise ValueError("raw and candidate must be aligned finite vectors")
    return raw + float(gain) * (candidate - raw)

def safety_project(command: np.ndarray, previous: np.ndarray | None, max_delta: float, max_step: float) -> np.ndarray:
    command = np.asarray(command, dtype=np.float32)
    if not np.isfinite(command).all(): raise ValueError("command contains non-finite values")
    if previous is not None:
        previous = np.asarray(previous, dtype=np.float32)
        command = previous + np.clip(command - previous, -max_step, max_step)
    return command
