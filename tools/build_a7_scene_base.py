#!/usr/bin/env python3
"""Shared calibrated A7 MuJoCo scene construction helpers.

This module intentionally contains no task scene entry point. Task-specific
builders import these helpers and declare their own assets and contracts.
"""
from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from interactive_mujoco_calibration import wrap_robot_root

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "assets/robots/linker_platform/sensorized/a7_dual_arm_l10_hands_cameras.mjcf.xml"
DEFAULT_CALIBRATION = ROOT / "config/sim/mujoco_sensor_calibration.json"
DEFAULT_LAYOUT = ROOT / "config/sim/a7_task_scene_layout.json"

DEFAULT_LAYOUT_VALUES = {
    "bodies": {
        "task_table": {"pos": [0.78, 0.0, -0.44], "quat": [1, 0, 0, 0]},
        "object_cube": {"pos": [0.64, -0.16, -0.36], "quat": [1, 0, 0, 0]},
        "object_cylinder": {"pos": [0.80, 0.03, -0.35], "quat": [1, 0, 0, 0]},
        "object_sphere": {"pos": [0.94, 0.17, -0.35], "quat": [1, 0, 0, 0]},
    }
}

def vec(values: list[float]) -> str:
    return " ".join(f"{float(x):.12g}" for x in values)


def xyaxes(direction: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in direction))
    backward = [-x / norm for x in direction]
    up = [0.0, 0.0, 1.0]
    dot = sum(up[i] * backward[i] for i in range(3))
    y = [up[i] - dot * backward[i] for i in range(3)]
    yn = math.sqrt(sum(x * x for x in y))
    y = [x / yn for x in y]
    x = [y[1] * backward[2] - y[2] * backward[1], y[2] * backward[0] - y[0] * backward[2], y[0] * backward[1] - y[1] * backward[0]]
    return x + y


def apply_calibration(root: ET.Element, payload: dict) -> None:
    anchor = next(x for x in root.iter("body") if x.get("name") == "robot_world_anchor")
    world = payload.get("robot_world", {})
    anchor.set("pos", vec(world.get("pos", [0, 0, 0])))
    anchor.set("quat", vec(world.get("quat", [1, 0, 0, 0])))
    for side in ("left", "right"):
        mount = next(x for x in anchor.iter("body") if x.get("name") == side + "_hand_mount")
        pose = payload.get("hand_mounts", {}).get(side, {})
        mount.set("pos", vec(pose.get("pos", [0, 0, 0])))
        mount.set("quat", vec(pose.get("quat", [1, 0, 0, 0])))
    for camera in root.iter("camera"):
        pose = payload.get("cameras", {}).get(camera.get("name"), {})
        if len(pose.get("pos", [])) == 3:
            camera.set("pos", vec(pose["pos"]))
        if len(pose.get("quat", [])) == 4 and all(math.isfinite(float(v)) for v in pose["quat"]):
            camera.set("quat", vec(pose["quat"]))


def merge_layout(path: Path | None) -> dict:
    values = json.loads(json.dumps(DEFAULT_LAYOUT_VALUES))
    if path is None or not path.is_file():
        return values
    payload = json.loads(path.read_text(encoding="utf-8"))
    for name, pose in payload.get("bodies", {}).items():
        if name not in values["bodies"]:
            values["bodies"][name] = {}
        if len(pose.get("pos", [])) == 3:
            values["bodies"][name]["pos"] = pose["pos"]
        if len(pose.get("quat", [])) == 4:
            values["bodies"][name]["quat"] = pose["quat"]
    return values
