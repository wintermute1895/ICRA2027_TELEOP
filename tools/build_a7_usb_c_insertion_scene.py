#!/usr/bin/env python3
"""Build the calibrated A7 + L10 MuJoCo scene for USB-C insertion teleoperation.

The robot model remains the source of truth for robot, hand and camera poses.
This builder adds only task entities in the table's local frame, so task-layout
changes cannot silently shift the calibrated robot coordinate system.
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco

from build_a7_scene_base import (
    DEFAULT_CALIBRATION,
    DEFAULT_LAYOUT,
    DEFAULT_MODEL,
    apply_calibration,
    merge_layout,
    vec,
    wrap_robot_root,
    xyaxes,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASK = ROOT / "config/sim/tasks/usb_c_laptop_insertion.json"
DEFAULT_OUTPUT = ROOT / "assets/robots/linker_platform/sensorized/a7_l10_usb_c_insertion.mjcf.xml"


def add_geom(parent: ET.Element, name: str, geom_type: str, pos: list[float], size: list[float], rgba: list[float], *, collision: bool = True) -> None:
    ET.SubElement(parent, "geom", {
        "name": name, "type": geom_type, "pos": vec(pos), "size": vec(size),
        "rgba": vec(rgba), "contype": "1" if collision else "0", "conaffinity": "1" if collision else "0",
    })


def add_table(parent: ET.Element, layout: dict) -> ET.Element:
    pose = layout["bodies"]["task_table"]
    table = ET.SubElement(parent, "body", {"name": "task_table", "pos": vec(pose["pos"]), "quat": vec(pose["quat"])})
    add_geom(table, "task_tabletop", "box", [0.0, 0.0, 0.0], [0.48, 0.52, 0.035], [0.33, 0.22, 0.12, 1.0])
    for y in (-0.43, 0.43):
        for x in (-0.34, 0.34):
            add_geom(table, f"task_table_leg_{x}_{y}", "box", [x, y, -0.40], [0.035, 0.035, 0.40], [0.22, 0.14, 0.08, 1.0])
    return table


def rotate_vector(quat: list[float], vector: list[float]) -> list[float]:
    w, x, y, z = (float(value) for value in quat)
    qv = [x, y, z]
    t = [2.0 * (qv[1] * vector[2] - qv[2] * vector[1]),
         2.0 * (qv[2] * vector[0] - qv[0] * vector[2]),
         2.0 * (qv[0] * vector[1] - qv[1] * vector[0])]
    return [vector[i] + w * t[i] + (qv[(i + 1) % 3] * t[(i + 2) % 3] - qv[(i + 2) % 3] * t[(i + 1) % 3]) for i in range(3)]


def add_connector_task(table: ET.Element, world: ET.Element, task: dict, table_pose: dict) -> None:
    p = task["parameters"]
    # These are table-local poses.  The receptacle faces the robot (-X); the
    # plug approaches along +X.  The laptop is deliberately set toward the
    # far edge, leaving a clear teleoperation approach corridor.
    laptop = ET.SubElement(table, "body", {"name": "task_laptop", "pos": "0.18 0 0.053"})
    add_geom(laptop, "task_laptop", "box", [0.0, 0, 0], [0.25, 0.18, 0.018], [0.12, 0.14, 0.16, 1])
    add_geom(laptop, "task_laptop_screen", "box", [0.20, 0, 0.117], [0.012, 0.18, 0.10], [0.05, 0.07, 0.09, 1], collision=False)

    channel_half_width = p["channel_width"] / 2
    channel_half_height = p["channel_height"] / 2
    # Laptop's near side is local -X.  The entry center is 45 mm over tabletop.
    receptacle = ET.SubElement(laptop, "body", {"name": "usb_c_receptacle", "pos": "-0.25 0 -0.008"})
    add_geom(receptacle, "usb_c_receptacle", "box", [0.008, 0, 0], [0.011, channel_half_width + 0.002, channel_half_height + 0.002], [0.04, 0.04, 0.045, 1], collision=False)
    ET.SubElement(receptacle, "site", {"name": "usb_c_receptacle_entry_site", "pos": "0 0 0", "size": "0.002", "rgba": "0.2 0.9 0.3 0.8"})
    ET.SubElement(receptacle, "site", {"name": "usb_c_receptacle_goal_site", "pos": vec([p["receptacle_goal_tip_x"], 0, 0]), "size": "0.002", "rgba": "0.1 0.6 1 0.8"})
    channel = ET.SubElement(receptacle, "body", {"name": "usb_c_insertion_channel"})
    add_geom(channel, "usb_c_insertion_channel", "box", [0.007, 0, 0], [0.007, channel_half_width, channel_half_height], [0.08, 0.09, 0.10, 0.35], collision=False)
    wall_x = p["channel_depth"] / 2
    add_geom(channel, "usb_c_channel_wall_left", "box", [wall_x, channel_half_width + 0.001, 0], [wall_x, 0.001, channel_half_height + 0.002], [0.25, 0.26, 0.28, 1])
    add_geom(channel, "usb_c_channel_wall_right", "box", [wall_x, -(channel_half_width + 0.001), 0], [wall_x, 0.001, channel_half_height + 0.002], [0.25, 0.26, 0.28, 1])
    add_geom(channel, "usb_c_channel_wall_top", "box", [wall_x, 0, channel_half_height + 0.001], [wall_x, channel_half_width + 0.002, 0.001], [0.25, 0.26, 0.28, 1])
    add_geom(channel, "usb_c_channel_wall_bottom", "box", [wall_x, 0, -(channel_half_height + 0.001)], [wall_x, channel_half_width + 0.002, 0.001], [0.25, 0.26, 0.28, 1])
    funnel = ET.SubElement(receptacle, "body", {"name": "usb_c_entry_funnel"})
    add_geom(funnel, "usb_c_entry_funnel", "box", [-0.010, 0, 0], [0.008, 0.014, 0.010], [0.15, 0.16, 0.18, 0.25], collision=False)
    add_geom(funnel, "usb_c_funnel_wall_left", "box", [-0.010, 0.014, 0], [0.008, 0.002, 0.010], [0.34, 0.36, 0.40, 1])
    add_geom(funnel, "usb_c_funnel_wall_right", "box", [-0.010, -0.014, 0], [0.008, 0.002, 0.010], [0.34, 0.36, 0.40, 1])

    table_pos = [float(value) for value in table_pose["pos"]]
    table_quat = [float(value) for value in table_pose["quat"]]
    plug_local = [-0.16, 0.0, 0.045]
    plug_world = [table_pos[i] + rotate_vector(table_quat, plug_local)[i] for i in range(3)]
    plug = ET.SubElement(world, "body", {"name": "usb_c_plug", "pos": vec(plug_world)})
    ET.SubElement(plug, "freejoint", {"name": "usb_c_plug_freejoint"})
    half_width, half_height = p["plug_width"] / 2, p["plug_height"] / 2
    add_geom(plug, "usb_c_plug", "box", [p["plug_length_from_root_to_tip"] / 2, 0, 0], [p["plug_length_from_root_to_tip"] / 2, half_width, half_height], [0.68, 0.70, 0.73, 1])
    add_geom(plug, "usb_c_plug_grip", "box", [0.020, 0, 0], [0.020, 0.010, 0.006], [0.08, 0.10, 0.12, 1])
    ET.SubElement(plug, "site", {"name": "usb_c_grasp_site", "pos": "0.020 0 0", "size": "0.004", "rgba": "1 0.7 0.1 0.8"})
    ET.SubElement(plug, "site", {"name": "usb_c_plug_tip_site", "pos": vec([p["plug_length_from_root_to_tip"], 0, 0]), "size": "0.002", "rgba": "1 0.2 0.2 0.8"})


def build(model: Path, calibration: Path, layout_path: Path, task_path: Path, output: Path) -> None:
    temporary = wrap_robot_root(model)
    try:
        tree = ET.parse(temporary)
    finally:
        temporary.unlink(missing_ok=True)
    root = tree.getroot()
    apply_calibration(root, json.loads(calibration.read_text(encoding="utf-8")))
    world = root.find("worldbody")
    if world is None:
        raise RuntimeError("MJCF has no worldbody")
    layout = merge_layout(layout_path)
    table = add_table(world, layout)
    add_connector_task(table, world, json.loads(task_path.read_text(encoding="utf-8")), layout["bodies"]["task_table"])
    ET.SubElement(world, "camera", {"name": "task_scene_rgb", "pos": "1.85 -2.20 0.35", "xyaxes": vec(xyaxes([0.62 - 1.85, 0.0 + 2.20, -0.40 - 0.35])), "resolution": "640 480", "fovy": "58"})
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)
    mujoco.MjModel.from_xml_path(str(output))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--layout", type=Path, default=DEFAULT_LAYOUT)
    parser.add_argument("--task", type=Path, default=DEFAULT_TASK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    for path in (args.model, args.calibration, args.task):
        if not path.is_file():
            parser.error(f"missing required input: {path}")
    build(args.model.resolve(), args.calibration.resolve(), args.layout.resolve(), args.task.resolve(), args.output.resolve())
    print(f"generated: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
