"""Linkerhand Python SDK for dexterous hand and robotic arm control.

Arm imports are lazy because they require optional ``pydantic``/kinematics
dependencies that are unrelated to hand-only tools such as O6 recording.
"""

from .exceptions import CANError, LinkerbotError, StateError, TimeoutError, ValidationError

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


def __getattr__(name):
    if name in {"L6", "L20lite", "O6", "L25"}:
        from .hand import L6, L20lite, L25, O6
        return {"L6": L6, "L20lite": L20lite, "O6": O6, "L25": L25}[name]
    if name in {"A7", "A7lite", "ControlMode", "Pose"}:
        from .arm import A7, A7lite, ControlMode, Pose
        return {"A7": A7, "A7lite": A7lite, "ControlMode": ControlMode, "Pose": Pose}[name]
    if name == "CanInterface":
        from .comm import CanInterface
        return CanInterface
    raise AttributeError(name)
