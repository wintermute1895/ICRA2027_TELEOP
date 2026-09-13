"""Runtime contract for the 7D, two-camera arm7 IMLE policy.

Task2 IMLE was trained on LinkerTA-degree JointState at 50 Hz with
obs_horizon=2, pred_horizon=16, action_horizon=8 and 20 overlap-selected
candidates.  Keeping the contract in one module prevents a radians ACT
checkpoint or a 13D arm+hand payload from reaching inference.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np


ACTION_CONTRACT = "arm7"
ACTION_UNITS = "degrees"
STATE_DIM = 7
ACTION_DIM = 7
OBS_HORIZON = 2
PRED_HORIZON = 16
ACTION_HORIZON = 8
CANDIDATE_COUNT = 20
IMAGE_HEIGHT = 480
IMAGE_WIDTH = 640
IMAGE_CHW = (3, IMAGE_HEIGHT, IMAGE_WIDTH)
CAMERA_KEYS = (
    "observation.images.main_rgb",
    "observation.images.auxiliary_rgb",
)
SCHEMA = "robot_teleop.imle-runtime/v1"


def _shape(feature: Any) -> tuple[int, ...] | None:
    value = getattr(feature, "shape", None)
    if value is None and isinstance(feature, Mapping):
        value = feature.get("shape")
    if value is None:
        return None
    return tuple(int(item) for item in value)


def normalize_action_units(value: Any) -> str:
    units = str(value if value is not None else ACTION_UNITS).strip().lower()
    if units in {"degree", "degrees", "deg"}:
        return "degrees"
    if units in {"radian", "radians", "rad"}:
        return "radians"
    raise ValueError(f"unsupported action_units={value!r}")


def ros_joint_positions(command: Any, action_units: Any = ACTION_UNITS) -> list[float]:
    """Publish a model command onto the LinkerTA-degree ROS boundary."""

    values = np.asarray(command, dtype=np.float32)
    if normalize_action_units(action_units) == "radians":
        values = np.rad2deg(values)
    return values.astype(float).tolist()


def should_reset_action_chunk(
    *,
    last_timestamp_ns: int | None,
    timestamp_ns: int,
    inference_hz: float,
    requested: bool = False,
) -> bool:
    """Reset the IMLE observation window and action queue after a gap."""

    if requested:
        return True
    if last_timestamp_ns is None or inference_hz <= 0:
        return False
    period_ns = 1_000_000_000.0 / float(inference_hz)
    return (timestamp_ns - last_timestamp_ns) > 1.5 * period_ns


def resolve_imle_root(config: Mapping[str, Any] | None = None) -> Path:
    """Locate the ICRA2027_TELEOP_IMLE checkout that owns robot_policy_imle."""

    values = config or {}
    configured = str(values.get("imle_root") or os.environ.get("IMLE_ROOT") or "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    repo_parent = Path(__file__).resolve().parents[1].parent
    candidates.extend(
        (
            repo_parent / "ICRA2027_TELEOP_IMLE",
            Path.home() / "桌面" / "ICRA2027_TELEOP_IMLE",
            Path("/home/dex/桌面/ICRA2027_TELEOP_IMLE"),
        )
    )
    for candidate in candidates:
        root = candidate.expanduser().resolve()
        if (root / "src" / "robot_policy_imle").is_dir():
            return root
    raise FileNotFoundError(
        "IMLE source not found. Set imle_root in the runtime YAML or IMLE_ROOT "
        "to the ICRA2027_TELEOP_IMLE checkout (must contain src/robot_policy_imle)"
    )


def validate_runtime_config(config: Mapping[str, Any]) -> None:
    """Reject a runtime YAML file that is not the trained arm7 IMLE contract."""

    schema = str(config.get("schema") or SCHEMA)
    if schema != SCHEMA:
        raise ValueError(f"IMLE runtime requires schema={SCHEMA!r}")
    if str(config.get("action_contract", ACTION_CONTRACT)) != ACTION_CONTRACT:
        raise ValueError(f"IMLE runtime requires action_contract={ACTION_CONTRACT!r}")
    if normalize_action_units(config.get("action_units", ACTION_UNITS)) != ACTION_UNITS:
        raise ValueError(f"IMLE runtime requires action_units={ACTION_UNITS!r}")
    if int(config.get("state_dim", STATE_DIM)) != STATE_DIM:
        raise ValueError(f"IMLE runtime requires state_dim={STATE_DIM}")
    if int(config.get("action_dim", ACTION_DIM)) != ACTION_DIM:
        raise ValueError(f"IMLE runtime requires action_dim={ACTION_DIM}")
    if int(config.get("obs_horizon", OBS_HORIZON)) != OBS_HORIZON:
        raise ValueError(f"IMLE runtime requires obs_horizon={OBS_HORIZON}")
    if int(config.get("pred_horizon", PRED_HORIZON)) != PRED_HORIZON:
        raise ValueError(f"IMLE runtime requires pred_horizon={PRED_HORIZON}")
    if int(config.get("action_horizon", ACTION_HORIZON)) != ACTION_HORIZON:
        raise ValueError(f"IMLE runtime requires action_horizon={ACTION_HORIZON}")
    if int(config.get("candidate_count", config.get("n_samples_per_condition", CANDIDATE_COUNT))) != CANDIDATE_COUNT:
        raise ValueError(f"IMLE runtime requires candidate_count={CANDIDATE_COUNT}")
    camera_keys = tuple((config.get("camera_keys") or {}).keys())
    if camera_keys != CAMERA_KEYS:
        raise ValueError(f"IMLE runtime requires camera_keys={list(CAMERA_KEYS)!r}")
    image_shape = tuple(int(item) for item in config.get("image_shape", (IMAGE_HEIGHT, IMAGE_WIDTH)))
    if image_shape != (IMAGE_HEIGHT, IMAGE_WIDTH):
        raise ValueError(f"IMLE runtime requires image_shape={[IMAGE_HEIGHT, IMAGE_WIDTH]!r}")


def validate_payload_config(runtime: Any) -> None:
    """Check the loaded deployment payload before the first inference."""

    def _get(name: str, default: Any) -> Any:
        if isinstance(runtime, Mapping):
            return runtime.get(name, default)
        return getattr(runtime, name, default)

    if int(_get("obs_horizon", OBS_HORIZON)) != OBS_HORIZON:
        raise ValueError(f"IMLE checkpoint obs_horizon must be {OBS_HORIZON}")
    if int(_get("pred_horizon", PRED_HORIZON)) != PRED_HORIZON:
        raise ValueError(f"IMLE checkpoint pred_horizon must be {PRED_HORIZON}")
    if int(_get("action_horizon", ACTION_HORIZON)) != ACTION_HORIZON:
        raise ValueError(f"IMLE checkpoint action_horizon must be {ACTION_HORIZON}")
    candidate_count = int(_get("candidate_count", _get("n_samples_per_condition", CANDIDATE_COUNT)))
    if candidate_count != CANDIDATE_COUNT:
        raise ValueError(f"IMLE checkpoint candidate_count must be {CANDIDATE_COUNT}")
    image_size = _get("image_size", (IMAGE_HEIGHT, IMAGE_WIDTH))
    if tuple(int(item) for item in image_size) != (IMAGE_HEIGHT, IMAGE_WIDTH):
        raise ValueError(f"IMLE checkpoint image_size must be {(IMAGE_HEIGHT, IMAGE_WIDTH)}")


def validate_state(value: Any) -> np.ndarray:
    state = np.asarray(value, dtype=np.float32)
    if state.shape != (STATE_DIM,) or not np.isfinite(state).all():
        raise ValueError(f"IMLE state requires {STATE_DIM} finite values")
    return state


def validate_action(value: Any) -> np.ndarray:
    action = np.asarray(value, dtype=np.float32)
    if action.shape != (ACTION_DIM,) or not np.isfinite(action).all():
        raise ValueError(f"IMLE action requires {ACTION_DIM} finite values")
    return action


def validate_image_chw(value: Any) -> np.ndarray:
    image = np.asarray(value)
    if image.shape != IMAGE_CHW:
        raise ValueError(f"IMLE image requires shape {IMAGE_CHW}, got {image.shape}")
    return image


def select_candidate_index(
    candidates: Any,
    prev_traj: Any | None,
    *,
    action_horizon: int = ACTION_HORIZON,
    rng: np.random.Generator | None = None,
) -> int:
    """Pick one of N predicted trajectories using first-step random / later overlap."""

    trajectories = np.asarray(candidates, dtype=np.float32)
    if trajectories.ndim != 3 or trajectories.shape[0] < 1:
        raise ValueError("IMLE candidates must have shape (N, pred_horizon, action_dim)")
    count = int(trajectories.shape[0])
    horizon = int(action_horizon)
    if prev_traj is None:
        generator = rng or np.random.default_rng()
        return int(generator.integers(0, count))
    previous = np.asarray(prev_traj, dtype=np.float32)
    if previous.ndim == 3:
        previous = previous[0]
    overlap = previous[horizon : horizon + horizon]
    starts = trajectories[:, :horizon]
    if overlap.shape != starts.shape[1:]:
        raise ValueError("IMLE overlap window does not match candidate start window")
    distances = np.sum((starts - overlap) ** 2, axis=(1, 2))
    return int(np.argmin(distances))


def executed_chunk(trajectory: Any, action_horizon: int = ACTION_HORIZON) -> np.ndarray:
    """Return the first action_horizon steps of a selected IMLE trajectory."""

    values = np.asarray(trajectory, dtype=np.float32)
    if values.ndim == 3:
        values = values[0]
    horizon = int(action_horizon)
    if values.ndim != 2 or values.shape[0] < horizon:
        raise ValueError("IMLE trajectory is shorter than action_horizon")
    return values[:horizon]
