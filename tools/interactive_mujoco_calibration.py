#!/usr/bin/env python3
"""Interactive MuJoCo calibration for A7 world pose and D435i/D405 cameras.

This tool deliberately does not command ROS2 or hardware. It edits only the
loaded simulation model. Press P to save a JSON calibration that the MJCF
generator can reload.
"""
from __future__ import annotations

import argparse
import json
import math
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "assets/robots/linker_platform/sensorized/a7_dual_arm_l10_hands_cameras.mjcf.xml"
DEFAULT_OUTPUT = ROOT / "config/sim/mujoco_sensor_calibration.json"
CAMERAS = ("head_d435i_rgb", "left_wrist_d405_rgb", "right_wrist_d405_rgb")
HAND_MOUNTS = ("left_hand_mount", "right_hand_mount")


def quaternion_from_euler(rpy: np.ndarray) -> np.ndarray:
    cr, sr = math.cos(rpy[0] / 2), math.sin(rpy[0] / 2)
    cp, sp = math.cos(rpy[1] / 2), math.sin(rpy[1] / 2)
    cy, sy = math.cos(rpy[2] / 2), math.sin(rpy[2] / 2)
    return np.array([cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy])


def wrap_robot_root(source: Path) -> Path:
    """Place all robot elements under a movable world anchor for visual setup."""
    tree = ET.parse(source)
    world = tree.getroot().find("worldbody")
    if world is None:
        raise RuntimeError("MJCF has no worldbody")
    keep = {"debug_floor", "key_light", "global_scene_rgb"}
    anchor = ET.Element("body", {"name": "robot_world_anchor", "pos": "0 0 0"})
    for child in list(world):
        if child.get("name") not in keep:
            world.remove(child)
            anchor.append(child)
    # Keep the hand installation independently adjustable while preserving
    # every hand joint and mesh below its original wrist link.
    for side in ("left", "right"):
        wrist_name = side.capitalize() + "_Wrist_Roll_Link"
        wrist = next((item for item in anchor.iter("body") if item.get("name") == wrist_name), None)
        if wrist is None:
            raise RuntimeError(f"missing wrist body: {wrist_name}")
        mount = ET.Element("body", {"name": side + "_hand_mount", "pos": "0 0 0", "quat": "1 0 0 0"})
        for child in list(wrist):
            is_hand_body = child.tag == "body" and child.get("name", "").startswith(side.capitalize() + "_Hand_")
            is_hand_base = child.tag == "geom" and child.get("mesh") == "hand_base_link"
            if is_hand_body or is_hand_base:
                wrist.remove(child)
                mount.append(child)
        wrist.append(mount)
    world.append(anchor)
    handle = tempfile.NamedTemporaryFile(prefix="a7_calibration_", suffix=".xml", delete=False)
    handle.close()
    tree.write(handle.name, encoding="utf-8", xml_declaration=True)
    return Path(handle.name)


def save(path: Path, model: mujoco.MjModel, root_id: int) -> None:
    cameras = {}
    for name in CAMERAS:
        camera_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, name)
        cameras[name] = {"pos": model.cam_pos[camera_id].tolist(), "quat": model.cam_quat[camera_id].tolist(), "fovy": float(model.cam_fovy[camera_id])}
    path.parent.mkdir(parents=True, exist_ok=True)
    hand_mounts = {}
    for side, body_name in zip(("left", "right"), HAND_MOUNTS):
        body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
        hand_mounts[side] = {"pos": model.body_pos[body_id].tolist(), "quat": model.body_quat[body_id].tolist()}
    payload = {
        "schema": "vist.mujoco-sensor-calibration/v2",
        "robot_world": {"pos": model.body_pos[root_id].tolist(), "quat": model.body_quat[root_id].tolist()},
        "hand_mounts": hand_mounts,
        "cameras": cameras,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"saved: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--load", type=Path, help="load a previously saved calibration before opening the viewer")
    parser.add_argument("--step-m", type=float, default=0.01)
    parser.add_argument("--step-deg", type=float, default=2.0)
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error(f"missing model: {args.model}")
    temporary = wrap_robot_root(args.model)
    try:
        model = mujoco.MjModel.from_xml_path(str(temporary))
    finally:
        temporary.unlink(missing_ok=True)
    data = mujoco.MjData(model)
    root_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "robot_world_anchor")
    if args.load is not None:
        if not args.load.is_file():
            parser.error(f"missing calibration: {args.load}")
        payload = json.loads(args.load.read_text(encoding="utf-8"))
        root = payload.get("robot_world", {})
        if len(root.get("pos", [])) == 3:
            model.body_pos[root_id] = root["pos"]
        if len(root.get("quat", [])) == 4:
            model.body_quat[root_id] = root["quat"]
        for name, pose in payload.get("cameras", {}).items():
            if name not in CAMERAS:
                continue
            cid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, name)
            if len(pose.get("pos", [])) == 3:
                model.cam_pos[cid] = pose["pos"]
            if len(pose.get("quat", [])) == 4:
                model.cam_quat[cid] = pose["quat"]
        for side, pose in payload.get("hand_mounts", {}).items():
            if side not in {"left", "right"}:
                continue
            bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, side + "_hand_mount")
            if len(pose.get("pos", [])) == 3:
                model.body_pos[bid] = pose["pos"]
            if len(pose.get("quat", [])) == 4:
                model.body_quat[bid] = pose["quat"]
        print(f"loaded: {args.load}")
    active = 0  # 0=root; 1=head; 2=left wrist; 3=right wrist; 4/5=hands
    step_m, step_rad = args.step_m, math.radians(args.step_deg)
    print("Controls: 0 robot | 1 head | 2 left wrist | 3 right wrist | 4 left hand | 5 right hand | WASD/RF translate | IJKLUO rotate | [ ] step | P save | Esc quit")

    def key_callback(keycode: int) -> None:
        nonlocal active, step_m, step_rad
        key = chr(keycode).lower() if 0 <= keycode < 256 else ""
        if key and key in "012345":
            active = int(key)
            labels = ("robot_world",) + CAMERAS + HAND_MOUNTS
            print("active:", labels[active])
            return
        if key == "[":
            step_m *= 0.5; step_rad *= 0.5; print(f"step={step_m:.4f}m, {math.degrees(step_rad):.2f}deg"); return
        if key == "]":
            step_m *= 2; step_rad *= 2; print(f"step={step_m:.4f}m, {math.degrees(step_rad):.2f}deg"); return
        if key == "p":
            save(args.output, model, root_id); return
        dp = np.zeros(3)
        move = {"w": (0, step_m), "s": (0, -step_m), "a": (1, step_m), "d": (1, -step_m), "r": (2, step_m), "f": (2, -step_m)}
        if key and key in move:
            axis, amount = move[key]; dp[axis] = amount
            if active == 0:
                model.body_pos[root_id] += dp
            elif active <= 3:
                model.cam_pos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, CAMERAS[active - 1])] += dp
            else:
                model.body_pos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, HAND_MOUNTS[active - 4])] += dp
            return
        rotate = {"i": (0, step_rad), "k": (0, -step_rad), "j": (1, step_rad), "l": (1, -step_rad), "u": (2, step_rad), "o": (2, -step_rad)}
        if key and key in rotate:
            axis, amount = rotate[key]
            delta = np.zeros(3); delta[axis] = amount
            quat = quaternion_from_euler(delta)
            if active == 0:
                result = np.empty(4)
                mujoco.mju_mulQuat(result, quat, model.body_quat[root_id])
                model.body_quat[root_id] = result
            elif active <= 3:
                cid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, CAMERAS[active - 1])
                result = np.empty(4)
                mujoco.mju_mulQuat(result, quat, model.cam_quat[cid])
                model.cam_quat[cid] = result
            else:
                bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, HAND_MOUNTS[active - 4])
                result = np.empty(4)
                mujoco.mju_mulQuat(result, quat, model.body_quat[bid])
                model.body_quat[bid] = result

    with mujoco.viewer.launch_passive(model, data, key_callback=key_callback) as viewer:
        while viewer.is_running():
            mujoco.mj_forward(model, data)
            viewer.sync()
            time.sleep(0.02)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
