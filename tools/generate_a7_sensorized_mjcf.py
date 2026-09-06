#!/usr/bin/env python3
"""Create a MuJoCo scene from the Aug-8 A7 arm/hand/camera URDF."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import mujoco

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URDF = ROOT / "assets/robots/linker_platform/sensorized/a7_dual_arm_l10_hands_cameras.urdf"
DEFAULT_OUTPUT = ROOT / "assets/robots/linker_platform/sensorized/a7_dual_arm_l10_hands_cameras.mjcf.xml"


def xyaxes(direction: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in direction))
    forward = [v / norm for v in direction]
    backward = [-v for v in forward]
    up = [0.0, 0.0, 1.0]
    dot = sum(up[i] * backward[i] for i in range(3))
    y = [up[i] - dot * backward[i] for i in range(3)]
    yn = math.sqrt(sum(v * v for v in y))
    y = [v / yn for v in y]
    x = [y[1] * backward[2] - y[2] * backward[1], y[2] * backward[0] - y[0] * backward[2], y[0] * backward[1] - y[1] * backward[0]]
    return x + y


def add_world_camera(spec: mujoco.MjSpec, name: str, position: list[float], target: list[float], fovy: float) -> None:
    spec.worldbody.add_camera(name=name, pos=position, xyaxes=xyaxes([target[i] - position[i] for i in range(3)]), resolution=[640, 480], fovy=fovy)


def add_body_camera(spec: mujoco.MjSpec, body_name: str, name: str, pose: dict[str, list[float]], fovy: float = 87.0) -> None:
    body = next((item for item in spec.bodies if item.name == body_name), None)
    if body is None:
        raise RuntimeError(f"camera body not found: {body_name}")
    body.add_camera(name=name, pos=pose["pos"], quat=pose["quat"], resolution=[640, 480], fovy=fovy)


DEFAULT_CALIBRATION = {
    "head_d435i_rgb": {"pos": [0.18, 0.0, 1.55], "quat": [0.690113, 0.154091, -0.154091, -0.690113], "fovy": 69.4},
    "left_wrist_d405_rgb": {"pos": [0.02, 0.04, -0.018], "quat": [0.632456, 0.316228, -0.316228, -0.632456], "fovy": 87.0},
    "right_wrist_d405_rgb": {"pos": [0.02, -0.04, -0.018], "quat": [0.632456, 0.316228, -0.316228, -0.632456], "fovy": 87.0},
}


def load_calibration(path: Path | None) -> dict[str, dict[str, list[float]]]:
    calibration = {name: value.copy() for name, value in DEFAULT_CALIBRATION.items()}
    if path is None:
        return calibration
    payload = json.loads(path.read_text(encoding="utf-8"))
    for name, default in calibration.items():
        candidate = payload.get("cameras", {}).get(name, {})
        if "pos" in candidate and len(candidate["pos"]) == 3:
            default["pos"] = candidate["pos"]
        if "quat" in candidate and len(candidate["quat"]) == 4:
            default["quat"] = candidate["quat"]
        if "fovy" in candidate:
            default["fovy"] = float(candidate["fovy"])
    return calibration


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=Path, default=DEFAULT_URDF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--calibration", type=Path, help="JSON emitted by interactive_mujoco_calibration.py")
    args = parser.parse_args()
    if not args.urdf.is_file():
        parser.error(f"missing URDF: {args.urdf}")
    if args.calibration is not None and not args.calibration.is_file():
        parser.error(f"missing calibration: {args.calibration}")
    calibration = load_calibration(args.calibration)
    spec = mujoco.MjSpec.from_file(str(args.urdf.resolve()))
    world = spec.worldbody
    world.add_geom(name="debug_floor", type=mujoco.mjtGeom.mjGEOM_PLANE, pos=[0, 0, -0.75], size=[2.5, 2.5, 0.1], rgba=[0.16, 0.18, 0.20, 1])
    world.add_light(name="key_light", type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL, pos=[1, -1.5, 2.4], dir=[-0.25, 0.35, -1], ambient=[0.35, 0.35, 0.35], diffuse=[0.85, 0.85, 0.85], castshadow=1)
    add_world_camera(spec, "global_scene_rgb", [1.65, -2.35, 1.25], [0, 0, 0.75], 58.0)
    head = calibration["head_d435i_rgb"]
    spec.worldbody.add_camera(name="head_d435i_rgb", pos=head["pos"], quat=head["quat"], resolution=[640, 480], fovy=head["fovy"])
    add_body_camera(spec, "Left_Wrist_Roll_Link", "left_wrist_d405_rgb", calibration["left_wrist_d405_rgb"], calibration["left_wrist_d405_rgb"]["fovy"])
    add_body_camera(spec, "Right_Wrist_Roll_Link", "right_wrist_d405_rgb", calibration["right_wrist_d405_rgb"], calibration["right_wrist_d405_rgb"]["fovy"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    spec.compile()
    spec.to_file(str(args.output.resolve()))
    print(f"generated: {args.output.resolve()}")
    print("cameras: global_scene_rgb, head_d435i_rgb, left_wrist_d405_rgb, right_wrist_d405_rgb")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
