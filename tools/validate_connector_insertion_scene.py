#!/usr/bin/env python3
"""Validate the standalone USB-C insertion scene without ROS2 or hardware."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import mujoco
import numpy as np

REQUIRED_BODIES = ["task_laptop", "usb_c_plug", "usb_c_receptacle", "usb_c_entry_funnel", "usb_c_insertion_channel"]
REQUIRED_GEOMS = REQUIRED_BODIES
REQUIRED_SITES = ["usb_c_grasp_site", "usb_c_plug_tip_site", "usb_c_receptacle_entry_site", "usb_c_receptacle_goal_site"]
ROOT = Path(__file__).resolve().parents[1]
TASK_JSON = ROOT / "config/sim/tasks/usb_c_laptop_insertion.json"


def name_id(model: mujoco.MjModel, obj: mujoco.mjtObj, name: str) -> int:
    return int(mujoco.mj_name2id(model, obj, name))


def load_task() -> dict:
    return json.loads(TASK_JSON.read_text(encoding="utf-8"))


def plug_pose(model: mujoco.MjModel, data: mujoco.MjData, root_x: float, y: float, angle: float = 0.0) -> None:
    body_id = name_id(model, mujoco.mjtObj.mjOBJ_BODY, "usb_c_plug")
    joint_id = int(model.body_jntadr[body_id])
    qpos = int(model.jnt_qposadr[joint_id])
    entry_z = load_task()["parameters"]["table_top_z"] + 0.045
    data.qpos[qpos:qpos + 3] = [root_x, y, entry_z]
    data.qpos[qpos + 3:qpos + 7] = [math.cos(angle / 2), 0, math.sin(angle / 2), 0]
    mujoco.mj_forward(model, data)


def contact_records(model: mujoco.MjModel, data: mujoco.MjData) -> list[dict]:
    records = []
    for index in range(data.ncon):
        contact = data.contact[index]
        g1, g2 = int(contact.geom1), int(contact.geom2)
        b1, b2 = int(model.geom_bodyid[g1]), int(model.geom_bodyid[g2])
        records.append({"geom_pair": [model.geom(g1).name, model.geom(g2).name], "body_pair": [model.body(b1).name, model.body(b2).name], "distance_m": float(contact.dist)})
    return records


def run_collision(model: mujoco.MjModel) -> dict:
    data = mujoco.MjData(model)
    p = load_task()["parameters"]
    root_goal = p["receptacle_goal_tip_x"] - p["plug_length_from_root_to_tip"]
    scenarios = [("outside", -0.14, 0.0, 0.0), ("offset", -0.095, 0.012, 0.0), ("aligned_goal", root_goal, 0.0, 0.0)]
    results = {}
    for label, x, y, angle in scenarios:
        plug_pose(model, data, x, y, angle)
        contacts = contact_records(model, data)
        results[label] = {"contact_count": len(contacts), "penetration_count": sum(c["distance_m"] < 0 for c in contacts), "contacts": contacts}
    plug_geom = name_id(model, mujoco.mjtObj.mjOBJ_GEOM, "usb_c_plug")
    receptacle_wall_geoms = [
        name_id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
        for name in ("usb_c_channel_wall_left", "usb_c_channel_wall_right", "usb_c_channel_wall_top", "usb_c_channel_wall_bottom", "usb_c_funnel_wall_left", "usb_c_funnel_wall_right")
    ]
    table_geom = name_id(model, mujoco.mjtObj.mjOBJ_GEOM, "task_table")
    laptop_geom = name_id(model, mujoco.mjtObj.mjOBJ_GEOM, "task_laptop")
    enabled_pairs = {
        "plug_receptacle": all(model.geom_contype[plug_geom] & model.geom_conaffinity[wall] and model.geom_contype[wall] & model.geom_conaffinity[plug_geom] for wall in receptacle_wall_geoms),
        "plug_table": bool(model.geom_contype[plug_geom] & model.geom_conaffinity[table_geom] and model.geom_contype[table_geom] & model.geom_conaffinity[plug_geom]),
        "plug_laptop": bool(model.geom_contype[plug_geom] & model.geom_conaffinity[laptop_geom] and model.geom_contype[laptop_geom] & model.geom_conaffinity[plug_geom]),
    }
    enabled = all(enabled_pairs.values())
    results["collision_groups_enabled"] = enabled_pairs
    results["passed"] = (results["outside"]["penetration_count"] == 0 and results["offset"]["contact_count"] > 0 and results["aligned_goal"]["penetration_count"] == 0 and enabled)
    return results


def render_contact_sheet(model: mujoco.MjModel, output: Path) -> None:
    from PIL import Image
    renderer = mujoco.Renderer(model, height=360, width=480)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    frames = []
    for name in ("global_view", "head_view", "wrist_view"):
        renderer.update_scene(data, camera=name)
        frames.append(Image.fromarray(renderer.render()))
    sheet = Image.new("RGB", (480 * 3, 360), "white")
    for index, frame in enumerate(frames):
        sheet.paste(frame, (index * 480, 0))
    sheet.save(output)
    renderer.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--require-named-contract", action="store_true")
    parser.add_argument("--check-collisions", action="store_true")
    parser.add_argument("--check-success-geometry", action="store_true")
    parser.add_argument("--render", type=Path)
    parser.add_argument("--report", type=Path, help="optional JSON report path")
    args = parser.parse_args()
    model = mujoco.MjModel.from_xml_path(str(args.scene.resolve()))
    task = load_task()
    report = {"schema": "connector-insertion-validation/v1", "scene": str(args.scene.resolve()), "checks": {}}
    if args.require_named_contract:
        missing = {"bodies": [n for n in REQUIRED_BODIES if name_id(model, mujoco.mjtObj.mjOBJ_BODY, n) < 0], "geoms": [n for n in REQUIRED_GEOMS if name_id(model, mujoco.mjtObj.mjOBJ_GEOM, n) < 0], "sites": [n for n in REQUIRED_SITES if name_id(model, mujoco.mjtObj.mjOBJ_SITE, n) < 0]}
        report["checks"]["named_contract"] = {"missing": missing, "passed": not any(missing.values())}
    if args.check_collisions:
        report["checks"]["collision_contract"] = run_collision(model)
    if args.check_success_geometry:
        p = task["parameters"]
        report["checks"]["success_geometry"] = {"lateral_tolerance_m": p["success_lateral_tolerance_m"], "angular_tolerance_deg": p["success_angular_tolerance_deg"], "minimum_insertion_depth_m": p["success_min_insertion_depth_m"], "passed": p["success_lateral_tolerance_m"] > 0 and p["success_angular_tolerance_deg"] > 0 and p["success_min_insertion_depth_m"] >= 0.006}
    if args.render:
        args.render.parent.mkdir(parents=True, exist_ok=True)
        render_contact_sheet(model, args.render)
        report["render"] = {"path": str(args.render.resolve()), "nonblank": args.render.stat().st_size > 1000}
    report["passed"] = all(check.get("passed", True) for check in report["checks"].values()) and report.get("render", {}).get("nonblank", True)
    report_path = args.report or args.scene.with_suffix(".validation.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Report: {report_path.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
