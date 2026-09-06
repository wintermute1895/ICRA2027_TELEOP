#!/usr/bin/env python3
"""Build a standalone parameterized MuJoCo USB-C laptop insertion scene."""
from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco

ROOT = Path(__file__).resolve().parents[1]


def vector(values: list[float]) -> str:
    return " ".join(f"{float(value):.9g}" for value in values)


def add_geom(parent: ET.Element, name: str, geom_type: str, pos: list[float], size: list[float], rgba: list[float], *, collision: bool = True, euler: list[float] | None = None) -> None:
    attrs = {"name": name, "type": geom_type, "pos": vector(pos), "size": vector(size), "rgba": vector(rgba), "contype": "1" if collision else "0", "conaffinity": "1" if collision else "0"}
    if euler is not None:
        attrs["euler"] = vector(euler)
    ET.SubElement(parent, "geom", attrs)


def camera_axes(camera: list[float], target: list[float]) -> str:
    forward = [target[i] - camera[i] for i in range(3)]
    norm = math.sqrt(sum(value * value for value in forward))
    backward = [-value / norm for value in forward]
    up = [0.0, 0.0, 1.0]
    dot = sum(up[i] * backward[i] for i in range(3))
    y = [up[i] - dot * backward[i] for i in range(3)]
    y_norm = math.sqrt(sum(value * value for value in y))
    y = [value / y_norm for value in y]
    x = [y[1] * backward[2] - y[2] * backward[1], y[2] * backward[0] - y[0] * backward[2], y[0] * backward[1] - y[1] * backward[0]]
    return vector(x + y)


def build(task_path: Path, output: Path) -> None:
    task = json.loads(task_path.read_text(encoding="utf-8"))
    p = task["parameters"]
    plug_half_width, plug_half_height = p["plug_width"] / 2, p["plug_height"] / 2
    channel_half_width, channel_half_height = p["channel_width"] / 2, p["channel_height"] / 2
    entry_z, initial_root_x = p["table_top_z"] + 0.045, -0.14
    scene = ET.Element("mujoco", {"model": task["task"]})
    ET.SubElement(scene, "compiler", {"angle": "degree", "coordinate": "local"})
    ET.SubElement(scene, "option", {"timestep": "0.002", "gravity": "0 0 -9.81"})
    default = ET.SubElement(scene, "default")
    ET.SubElement(default, "geom", {"friction": "0.9 0.02 0.001", "solref": "0.004 1", "solimp": "0.95 0.99 0.001"})
    world = ET.SubElement(scene, "worldbody")
    ET.SubElement(world, "light", {"name": "task_key_light", "pos": "0.10 -0.35 0.70", "dir": "0.0 0.3 -0.7", "directional": "true", "diffuse": "0.9 0.9 0.9"})
    add_geom(world, "task_floor", "plane", [0, 0, 0], [2, 2, 0.1], [0.13, 0.15, 0.17, 1])
    table = ET.SubElement(world, "body", {"name": "task_table", "pos": "0 0 0"})
    add_geom(table, "task_table", "box", [0.16, 0, 0], [0.42, 0.30, p["table_top_z"]], [0.34, 0.25, 0.16, 1])
    laptop = ET.SubElement(world, "body", {"name": "task_laptop", "pos": "0 0 0"})
    add_geom(laptop, "task_laptop", "box", [0.18, 0, p["table_top_z"] + 0.018], [0.25, 0.18, 0.018], [0.12, 0.14, 0.16, 1])
    add_geom(laptop, "task_laptop_screen", "box", [0.38, 0, p["table_top_z"] + 0.135], [0.012, 0.18, 0.10], [0.05, 0.07, 0.09, 1], collision=False)
    receptacle = ET.SubElement(laptop, "body", {"name": "usb_c_receptacle", "pos": vector([0, 0, entry_z])})
    add_geom(receptacle, "usb_c_receptacle", "box", [0.008, 0, 0], [0.011, channel_half_width + 0.002, channel_half_height + 0.002], [0.04, 0.04, 0.045, 1], collision=False)
    ET.SubElement(receptacle, "site", {"name": "usb_c_receptacle_entry_site", "pos": "0 0 0", "size": "0.002", "rgba": "0.2 0.9 0.3 0.8"})
    ET.SubElement(receptacle, "site", {"name": "usb_c_receptacle_goal_site", "pos": vector([p["receptacle_goal_tip_x"], 0, 0]), "size": "0.002", "rgba": "0.1 0.6 1 0.8"})
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
    plug = ET.SubElement(world, "body", {"name": "usb_c_plug", "pos": vector([initial_root_x, 0, entry_z])})
    ET.SubElement(plug, "freejoint", {"name": "usb_c_plug_freejoint"})
    add_geom(plug, "usb_c_plug", "box", [p["plug_length_from_root_to_tip"] / 2, 0, 0], [p["plug_length_from_root_to_tip"] / 2, plug_half_width, plug_half_height], [0.68, 0.70, 0.73, 1])
    add_geom(plug, "usb_c_plug_grip", "box", [0.020, 0, 0], [0.020, 0.010, 0.006], [0.08, 0.10, 0.12, 1])
    ET.SubElement(plug, "site", {"name": "usb_c_grasp_site", "pos": "0.020 0 0", "size": "0.004", "rgba": "1 0.7 0.1 0.8"})
    ET.SubElement(plug, "site", {"name": "usb_c_plug_tip_site", "pos": vector([p["plug_length_from_root_to_tip"], 0, 0]), "size": "0.002", "rgba": "1 0.2 0.2 0.8"})
    target = [0.02, 0, entry_z]
    for name, pos in (("global_view", [0.62, -0.70, 0.42]), ("head_view", [0.35, -0.32, 0.23]), ("wrist_view", [-0.22, -0.20, 0.12])):
        ET.SubElement(world, "camera", {"name": name, "pos": vector(pos), "xyaxes": camera_axes(pos, target), "fovy": "48"})
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(scene, space="  ")
    ET.ElementTree(scene).write(output, encoding="utf-8", xml_declaration=True)
    mujoco.MjModel.from_xml_path(str(output))
    print(f"generated: {output.resolve()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="usb_c_laptop_insertion")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="optional baseline build JSON report")
    args = parser.parse_args()
    task_path = ROOT / "config/sim/tasks" / f"{args.task}.json"
    if not task_path.is_file():
        parser.error(f"unknown task: {args.task}")
    build(task_path, args.output.resolve())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"schema": "connector-insertion-build/v1", "task": args.task, "output": str(args.output.resolve()), "mujoco_compiled": True, "passed": True}, indent=2) + "\n", encoding="utf-8")
        print(f"Report: {args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
