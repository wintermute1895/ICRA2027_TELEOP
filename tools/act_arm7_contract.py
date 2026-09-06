"""Runtime contract for the 7D, two-camera ACT policy.

The button-press policy was trained with seven right-arm joints and the two
named RGB inputs below.  Keeping this contract in one small module prevents a
13D arm+hand checkpoint or a single-camera stream from reaching inference.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


ACTION_CONTRACT = "arm7"
STATE_DIM = 7
ACTION_DIM = 7
IMAGE_HEIGHT = 480
IMAGE_WIDTH = 640
IMAGE_CHW = (3, IMAGE_HEIGHT, IMAGE_WIDTH)
CAMERA_KEYS = (
    "observation.images.main_rgb",
    "observation.images.auxiliary_rgb",
)


def _shape(feature: Any) -> tuple[int, ...] | None:
    value = getattr(feature, "shape", None)
    if value is None and isinstance(feature, Mapping):
        value = feature.get("shape")
    if value is None:
        return None
    return tuple(int(item) for item in value)


def validate_runtime_config(config: Mapping[str, Any]) -> None:
    """Reject a runtime YAML file that is not the trained arm7 contract."""

    if str(config.get("action_contract", ACTION_CONTRACT)) != ACTION_CONTRACT:
        raise ValueError(f"ACT runtime requires action_contract={ACTION_CONTRACT!r}")
    if int(config.get("state_dim", STATE_DIM)) != STATE_DIM:
        raise ValueError(f"ACT runtime requires state_dim={STATE_DIM}")
    if int(config.get("action_dim", ACTION_DIM)) != ACTION_DIM:
        raise ValueError(f"ACT runtime requires action_dim={ACTION_DIM}")
    camera_keys = tuple((config.get("camera_keys") or {}).keys())
    if camera_keys != CAMERA_KEYS:
        raise ValueError(f"ACT runtime requires camera_keys={list(CAMERA_KEYS)!r}")
    image_shape = tuple(int(item) for item in config.get("image_shape", (IMAGE_HEIGHT, IMAGE_WIDTH)))
    if image_shape != (IMAGE_HEIGHT, IMAGE_WIDTH):
        raise ValueError(f"ACT runtime requires image_shape={[IMAGE_HEIGHT, IMAGE_WIDTH]!r}")


def validate_policy_config(policy_config: Any) -> None:
    """Check LeRobot's loaded feature schema before the first inference."""

    inputs = getattr(policy_config, "input_features", {})
    outputs = getattr(policy_config, "output_features", {})
    expected_inputs = {
        "observation.state": (STATE_DIM,),
        CAMERA_KEYS[0]: IMAGE_CHW,
        CAMERA_KEYS[1]: IMAGE_CHW,
    }
    for key, expected in expected_inputs.items():
        actual = _shape(inputs.get(key)) if hasattr(inputs, "get") else None
        if actual != expected:
            raise ValueError(f"ACT checkpoint feature {key!r} has shape {actual}, expected {expected}")
    actual_action = _shape(outputs.get("action")) if hasattr(outputs, "get") else None
    if actual_action != (ACTION_DIM,):
        raise ValueError(f"ACT checkpoint action has shape {actual_action}, expected {(ACTION_DIM,)}")


def validate_state(value: Any) -> np.ndarray:
    state = np.asarray(value, dtype=np.float32)
    if state.shape != (STATE_DIM,) or not np.isfinite(state).all():
        raise ValueError(f"ACT state requires {STATE_DIM} finite values")
    return state


def validate_action(value: Any) -> np.ndarray:
    action = np.asarray(value, dtype=np.float32)
    if action.shape != (ACTION_DIM,) or not np.isfinite(action).all():
        raise ValueError(f"ACT action requires {ACTION_DIM} finite values")
    return action


def validate_image_chw(value: Any) -> np.ndarray:
    image = np.asarray(value)
    if image.shape != IMAGE_CHW:
        raise ValueError(f"ACT image requires shape {IMAGE_CHW}, got {image.shape}")
    return image
