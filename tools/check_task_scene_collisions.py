#!/usr/bin/env python3
"""Validate a DexCatch joint trajectory against the MuJoCo task scene.

This is a scene-level validator, deliberately separate from DexCatch's arm
self-collision checker. It consumes canonical or vendor joint names, writes
the trajectory into the sensorized MuJoCo model, and reports only contacts
between robot/hand bodies and the table or task objects.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENE = ROOT / "assets/robots/linker_platform/sensorized/a7_l10_task_scene.mjcf.xml"
ENV_BODIES = {"task_table", "object_cube", "object_cylinder", "object_sphere"}
VENDOR_JOINTS = {
    "left": [
        "Left_Shoulder_Pitch_Joint", "Left_Shoulder_Roll_Joint",
        "Left_Shoulder_Yaw_Joint", "Left_Elbow_Pitch_Joint",
        "Left_Wrist_Yaw_Joint", "Left_Wrist_Roll_Joint",
        "Left_Wrist_Pitch_Joint",
    ],
    "right": [
        "Right_Shoulder_Pitch_Joint", "Right_Shoulder_Roll_Joint",
        "Right_Shoulder_Yaw_Joint", "Right_Elbow_Pitch_Joint",
        "Right_Wrist_Yaw_Joint", "Right_Wrist_Roll_Joint",
        "Right_Wrist_Pitch_Joint",
    ],
}
CANONICAL_JOINTS = {
    **{f"L{i}_Joint": name for i, name in enumerate(VENDOR_JOINTS["left"], 1)},
    **{f"R{i}_Joint": name for i, name in enumerate(VENDOR_JOINTS["right"], 1)},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, default=DEFAULT_SCENE)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clearance-threshold-m", type=float, default=0.01)
    parser.add_argument("--fail-on-near", action="store_true")
    return parser.parse_args()


def body_name(model: mujoco.MjModel, geom_id: int) -> str:
    return str(model.body(model.geom_bodyid[geom_id]).name)


def geom_name(model: mujoco.MjModel, geom_id: int) -> str:
    name = model.geom(geom_id).name
    return str(name or f"geom_{geom_id}")


def is_robot_body(name: str) -> bool:
    return name.startswith(("Left_", "Right_", "Body_", "left_hand", "right_hand"))


def trajectory_samples(plan: dict[str, Any]) -> list[dict[str, Any]]:
    trajectory = plan.get("trajectory", plan)
    samples = trajectory.get("samples", [])
    if not isinstance(samples, list) or not samples:
        raise ValueError("plan contains no trajectory samples")
    return samples


def main() -> int:
    args = parse_args()
    if not args.scene.is_file():
        raise SystemExit(f"scene not found: {args.scene}")
    if not args.plan.is_file():
        raise SystemExit(f"plan not found: {args.plan}")
    if args.clearance_threshold_m < 0:
        raise SystemExit("--clearance-threshold-m must be non-negative")

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    samples = trajectory_samples(plan)
    joint_names = list(plan.get("trajectory", plan).get("joint_names", []))
    if len(joint_names) != 7:
        raise SystemExit("plan must contain seven joint_names")
    arm = str(plan.get("arm", plan.get("trajectory", {}).get("arm", "")))
    if arm not in VENDOR_JOINTS:
        raise SystemExit("plan arm must be left or right")

    model = mujoco.MjModel.from_xml_path(str(args.scene.resolve()))
    data = mujoco.MjData(model)
    addresses: dict[str, int] = {}
    for canonical in joint_names:
        vendor = CANONICAL_JOINTS.get(canonical, canonical)
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, vendor)
        if joint_id < 0:
            raise SystemExit(f"scene missing trajectory joint: {canonical} -> {vendor}")
        addresses[canonical] = int(model.jnt_qposadr[joint_id])

    table_and_objects = set(ENV_BODIES)
    near_contacts: list[dict[str, Any]] = []
    penetrations: list[dict[str, Any]] = []
    per_environment: dict[str, int] = {name: 0 for name in sorted(ENV_BODIES)}
    minimum_clearance = float("inf")
    minimum_record: dict[str, Any] | None = None

    for sample_index, sample in enumerate(samples):
        values = sample.get("joints_rad")
        if not isinstance(values, list) or len(values) != 7:
            raise SystemExit(f"sample {sample_index} does not contain seven joints_rad")
        for canonical, value in zip(joint_names, values):
            data.qpos[addresses[canonical]] = float(value)
        mujoco.mj_forward(model, data)
        mujoco.mj_collision(model, data)
        for contact_index in range(data.ncon):
            contact = data.contact[contact_index]
            first_body = body_name(model, int(contact.geom1))
            second_body = body_name(model, int(contact.geom2))
            if first_body in table_and_objects and second_body in table_and_objects:
                continue
            environment = first_body if first_body in table_and_objects else second_body if second_body in table_and_objects else None
            robot = second_body if environment == first_body else first_body if environment == second_body else None
            if environment is None or robot is None or not is_robot_body(robot):
                continue
            distance = float(contact.dist)
            record = {
                "sample_index": sample_index,
                "time_s": float(sample.get("time_s", sample_index)),
                "environment_body": environment,
                "robot_body": robot,
                "geom_pair": [geom_name(model, int(contact.geom1)), geom_name(model, int(contact.geom2))],
                "distance_m": distance,
            }
            per_environment[environment] += 1
            if distance < minimum_clearance:
                minimum_clearance = distance
                minimum_record = record
            if distance < 0.0:
                penetrations.append(record)
            elif distance < args.clearance_threshold_m:
                near_contacts.append(record)

    report = {
        "schema": "vist.sim-task-collision-report/v1",
        "source_domain": "sim",
        "hardware_accessed": False,
        "scene": str(args.scene.resolve()),
        "plan": str(args.plan.resolve()),
        "arm": arm,
        "checked_samples": len(samples),
        "environment_bodies": sorted(ENV_BODIES),
        "clearance_threshold_m": args.clearance_threshold_m,
        "contacts": {
            "environment_contact_count": len(near_contacts) + len(penetrations),
            "near_contact_count": len(near_contacts),
            "penetration_count": len(penetrations),
            "per_environment_body": per_environment,
            "minimum_clearance_m": None if minimum_record is None else minimum_clearance,
            "minimum_clearance": minimum_record,
        },
        "gate": {
            "passed": not penetrations and (not args.fail_on_near or not near_contacts),
            "failure_reasons": (["penetration"] if penetrations else []) + (["clearance_below_threshold"] if args.fail_on_near and near_contacts else []),
        },
        "near_contacts": near_contacts[:100],
        "penetrations": penetrations[:100],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    status = "PASS" if report["gate"]["passed"] else "FAIL"
    print(f"{status}: checked {len(samples)} samples; environment contacts={report['contacts']['environment_contact_count']}; penetrations={len(penetrations)}")
    print(f"Report: {args.output.resolve()}")
    return 0 if report["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
