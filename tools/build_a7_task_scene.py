#!/usr/bin/env python3
"""Build a static MuJoCo task scene around the calibrated A7 robot."""
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
DEFAULT_OUTPUT = ROOT / "assets/robots/linker_platform/sensorized/a7_l10_task_scene.mjcf.xml"

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


def add_geom(parent: ET.Element, name: str, pos: list[float], size: list[float], rgba: list[float], geom_type: str = "box") -> None:
    ET.SubElement(parent, "geom", {"name": name, "type": geom_type, "pos": vec(pos), "size": vec(size), "rgba": vec(rgba), "contype": "1", "conaffinity": "1"})


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


def build(model: Path, calibration: Path, output: Path, layout_path: Path | None = None) -> None:
    temporary = wrap_robot_root(model)
    try:
        tree = ET.parse(temporary)
    finally:
        temporary.unlink(missing_ok=True)
    root = tree.getroot()
    payload = json.loads(calibration.read_text(encoding="utf-8"))
    apply_calibration(root, payload)
    layout = merge_layout(layout_path)
    world = root.find("worldbody")
    if world is None:
        raise RuntimeError("MJCF has no worldbody")

    # The calibrated robot's task-facing direction is +X. The table body is
    # an independently editable scene entity; all dimensions below are local.
    table_pose = layout["bodies"]["task_table"]
    table = ET.SubElement(world, "body", {"name": "task_table", "pos": vec(table_pose["pos"]), "quat": vec(table_pose["quat"])})
    add_geom(table, "task_tabletop", [0.0, 0.0, 0.0], [0.48, 0.52, 0.035], [0.33, 0.22, 0.12, 1.0])
    for y in (-0.43, 0.43):
        for x in (-0.34, 0.34):
            add_geom(table, f"task_table_leg_{x}_{y}", [x, y, -0.40], [0.035, 0.035, 0.40], [0.22, 0.14, 0.08, 1.0])

    object_specs = {
        "object_cube": ("box", [0.045, 0.045, 0.045], [0.1, 0.45, 0.9, 1.0]),
        "object_cylinder": ("cylinder", [0.045, 0.055], [0.9, 0.45, 0.08, 1.0]),
        "object_sphere": ("sphere", [0.055], [0.2, 0.75, 0.25, 1.0]),
    }
    for name, (geom_type, size, rgba) in object_specs.items():
        pose = layout["bodies"][name]
        body = ET.SubElement(world, "body", {"name": name, "pos": vec(pose["pos"]), "quat": vec(pose["quat"])})
        add_geom(body, name + "_geom", [0.0, 0.0, 0.0], size, rgba, geom_type)

    # A dedicated scene camera makes the task surface visible without changing
    # the calibrated robot-mounted cameras.
    ET.SubElement(world, "camera", {"name": "task_scene_rgb", "pos": "1.85 -2.20 0.35", "xyaxes": vec(xyaxes([0.62 - 1.85, 0.0 + 2.20, -0.40 - 0.35])), "resolution": "640 480", "fovy": "58"})
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)
    print(f"generated: {output.resolve()}")
    print("scene objects: task_tabletop, object_cube, object_cylinder, object_sphere")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--layout", type=Path, default=DEFAULT_LAYOUT, help="optional scene entity layout JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.model.is_file() or not args.calibration.is_file():
        parser.error("model and calibration must exist")
    build(args.model.resolve(), args.calibration.resolve(), args.output.resolve(), args.layout.resolve() if args.layout.is_file() else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
