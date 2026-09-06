#!/usr/bin/env python3
"""Edit reusable MuJoCo task-scene entities with grouped selection."""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT / "assets/robots/linker_platform/sensorized/a7_l10_task_scene.mjcf.xml"
DEFAULT_LAYOUT = ROOT / "config/sim/a7_task_scene_layout.json"
GROUPS = {
    "scene": ("task_table",),
    "objects": ("object_cube", "object_cylinder", "object_sphere"),
}
GROUP_ORDER = tuple(GROUPS)


def quat_from_axis(axis: int, radians: float) -> np.ndarray:
    half = radians / 2
    result = np.zeros(4)
    result[0] = math.cos(half)
    result[axis + 1] = math.sin(half)
    return result


def save_layout(path: Path, model: mujoco.MjModel) -> None:
    bodies = {}
    for names in GROUPS.values():
        for name in names:
            body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
            bodies[name] = {"pos": model.body_pos[body_id].tolist(), "quat": model.body_quat[body_id].tolist()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": "vist.mujoco-task-layout/v1", "bodies": bodies}, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"[SAVED] {path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--layout", type=Path, default=DEFAULT_LAYOUT)
    parser.add_argument("--step-m", type=float, default=0.01)
    parser.add_argument("--step-deg", type=float, default=2.0)
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error(f"missing scene model: {args.model}")
    model = mujoco.MjModel.from_xml_path(str(args.model))
    data = mujoco.MjData(model)
    active_group, active_index, choosing_group = "scene", 0, False
    step_m, step_rad = args.step_m, math.radians(args.step_deg)

    def status(prefix: str = "SELECT") -> None:
        name = GROUPS[active_group][active_index]
        print(f"[{prefix}] group={active_group} ({GROUP_ORDER.index(active_group)+1}/{len(GROUP_ORDER)}) item={active_index} name={name} step={step_m:.4f}m/{math.degrees(step_rad):.2f}deg", flush=True)

    print("Scene editor: G then 1=scene or 2=objects; then 0..9 selects item. WASD/RF translate, IJKLUO rotate, [/] step, P save, H help.", flush=True)
    status()

    def key_callback(keycode: int) -> None:
        nonlocal active_group, active_index, choosing_group, step_m, step_rad
        key = chr(keycode).lower() if 0 <= keycode < 256 else ""
        if key == "g":
            choosing_group = True
            print("[GROUP] choose: 1=scene, 2=objects", flush=True)
            return
        if choosing_group and key and key.isdigit():
            group_index = int(key) - 1
            if 0 <= group_index < len(GROUP_ORDER):
                active_group, active_index = GROUP_ORDER[group_index], 0
                choosing_group = False
                status()
            else:
                print("[GROUP] invalid group index", flush=True)
            return
        if key and key.isdigit():
            item_index = int(key)
            if item_index < len(GROUPS[active_group]):
                active_index = item_index
                status()
            else:
                print(f"[SELECT] {active_group} has {len(GROUPS[active_group])} item(s)", flush=True)
            return
        if key == "h":
            print("[HELP] G->group number->item number; WASD/RF XYZ; I/K roll, J/L pitch, U/O yaw; [/] step; P save", flush=True)
            return
        if key == "[":
            step_m *= 0.5; step_rad *= 0.5; status("STEP"); return
        if key == "]":
            step_m *= 2; step_rad *= 2; status("STEP"); return
        if key == "p":
            save_layout(args.layout, model); return
        body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, GROUPS[active_group][active_index])
        move = {"w": (0, step_m), "s": (0, -step_m), "a": (1, step_m), "d": (1, -step_m), "r": (2, step_m), "f": (2, -step_m)}
        if key and key in move:
            axis, amount = move[key]
            model.body_pos[body_id, axis] += amount
            status("MOVE")
            return
        rotate = {"i": (0, step_rad), "k": (0, -step_rad), "j": (1, step_rad), "l": (1, -step_rad), "u": (2, step_rad), "o": (2, -step_rad)}
        if key and key in rotate:
            axis, amount = rotate[key]
            result = np.empty(4)
            mujoco.mju_mulQuat(result, quat_from_axis(axis, amount), model.body_quat[body_id])
            model.body_quat[body_id] = result
            status("ROTATE")

    with mujoco.viewer.launch_passive(model, data, key_callback=key_callback) as viewer:
        while viewer.is_running():
            mujoco.mj_forward(model, data)
            viewer.sync()
            time.sleep(0.02)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
