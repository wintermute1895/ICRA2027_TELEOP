"""Linkerhand Python SDK for dexterous hand and robotic arm control.

Arm modules depend on SciPy and other kinematics packages. Keep those imports
lazy so hand-only deployments (including O6) do not fail during package import
because an unrelated arm dependency is absent.
"""

from .exceptions import (
    CANError,
    LinkerbotError,
    StateError,
    TimeoutError,
    ValidationError,
)

_HAND_EXPORTS = {"L6", "L20lite", "O6", "L25"}
_ARM_EXPORTS = {"A7", "A7lite", "Pose", "ControlMode"}


def __getattr__(name):
    if name in _HAND_EXPORTS:
        from .hand import L6, L25, L20lite, O6
        return {"L6": L6, "L25": L25, "L20lite": L20lite, "O6": O6}[name]
    if name in _ARM_EXPORTS:
        from .arm import A7, A7lite, ControlMode, Pose
        return {"A7": A7, "A7lite": A7lite, "ControlMode": ControlMode, "Pose": Pose}[name]
    if name == "CanInterface":
        from .comm import CanInterface
        return CanInterface
    raise AttributeError(name)

__all__ = [
    "LinkerbotError",
    "TimeoutError",
    "CANError",
    "ValidationError",
    "StateError",
    "L6",
    "L20lite",
    "O6",
    "L25",
    "A7",
    "A7lite",
    "Pose",
    "ControlMode",
    "CanInterface",
]
