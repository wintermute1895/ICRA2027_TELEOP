#!/usr/bin/env python3
"""Render camera-placement candidates for a MuJoCo URDF/MJCF model.

This is a read-only visualization tool: it never starts ROS2, CAN, a robot
driver, or a real camera. It is useful for tuning a head/workspace camera
before committing extrinsics to the sensorized model.
"""
from __future__ import annotations

import argparse
import math
import re
import tempfile
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw


def axes(direction: list[float]) -> list[float]:
    forward = np.asarray(direction, dtype=float)
    forward /= np.linalg.norm(forward)
    backward = -forward
    up = np.asarray([0.0, 0.0, 1.0])
    y = up - np.dot(up, backward) * backward
    y /= np.linalg.norm(y)
    x = np.cross(y, backward)
    return [*x.tolist(), *y.tolist()]


def normalized_model(source: Path, mesh_root: Path | None) -> Path:
    text = source.read_text(encoding="utf-8")
    if mesh_root is not None:
        text = text.replace(
            "/mnt/F/ICRA2027_TELEOP/IROS_teleop/config/combined_robot/meshes/arm/",
            str(mesh_root.resolve()) + "/",
        )
    else:
        # Resolve the common ROS package URI form used by the ICRA assets.
        # Prefer the arm subdirectory when the URDF sits beside a combined
        # robot asset; otherwise use a normal sibling meshes directory.
        candidates = [source.parent / "meshes/arm", source.parent / "meshes"]
        selected = next((item for item in candidates if item.is_dir()), None)
        if selected is not None:
            text = re.sub(
                r"package://[^/]+/meshes/",
                str(selected.resolve()) + "/",
                text,
            )
    handle = tempfile.NamedTemporaryFile("w", suffix=source.suffix, delete=False)
    handle.write(text)
    handle.close()
    return Path(handle.name)


def render(source: Path, output: Path, mesh_root: Path | None, target: list[float], width: int, height: int) -> None:
    normalized = normalized_model(source, mesh_root)
    spec = mujoco.MjSpec.from_file(str(normalized))
    world = spec.worldbody
    if not any(item.name == "debug_floor" for item in spec.geoms):
        world.add_geom(name="debug_floor", type=mujoco.mjtGeom.mjGEOM_PLANE, pos=[0, 0, -0.72], size=[2.5, 2.5, 0.1], rgba=[0.16, 0.18, 0.20, 1])
    if not any(item.name == "debug_key" for item in spec.lights):
        world.add_light(name="debug_key", type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL, pos=[1.0, -1.5, 2.4], dir=[-0.25, 0.35, -1.0], ambient=[0.35, 0.35, 0.35], diffuse=[0.85, 0.85, 0.85], specular=[0.15, 0.15, 0.15], castshadow=1)
    if not any(item.name == "debug_fill" for item in spec.lights):
        world.add_light(name="debug_fill", type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL, pos=[-1.0, 1.0, 1.6], dir=[0.3, -0.25, -1.0], ambient=[0.18, 0.18, 0.18], diffuse=[0.45, 0.48, 0.52], specular=[0.05, 0.05, 0.05], castshadow=0)
    model = spec.compile()
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    candidates = [
        ("front_left", [1.55, -2.30, 1.35]),
        ("front_center", [1.85, -0.05, 1.20]),
        ("front_right", [1.55, 2.30, 1.35]),
        ("high_left", [1.25, -2.10, 2.00]),
        ("high_center", [1.55, 0.0, 1.85]),
        ("high_right", [1.25, 2.10, 2.00]),
    ]
    output.mkdir(parents=True, exist_ok=True)
    images: list[Image.Image] = []
    for name, position in candidates:
        camera = spec.worldbody.add_camera(
            name="candidate_" + name,
            pos=position,
            xyaxes=axes([target[i] - position[i] for i in range(3)]),
            resolution=[width, height],
            fovy=58,
        )
        # Compile a fresh model so each named camera is available.
        candidate_model = spec.compile()
        candidate_data = mujoco.MjData(candidate_model)
        mujoco.mj_forward(candidate_model, candidate_data)
        renderer = mujoco.Renderer(candidate_model, height=height, width=width)
        renderer.update_scene(candidate_data, camera="candidate_" + name)
        image = Image.fromarray(renderer.render()).convert("RGB")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 210, 26), fill=(0, 0, 0))
        draw.text((8, 7), f"{name}  target={target}", fill=(255, 255, 255))
        image.save(output / f"{name}.png")
        images.append(image)

    sheet = Image.new("RGB", (width * 3, height * 2), (20, 20, 20))
    for index, image in enumerate(images):
        sheet.paste(image, ((index % 3) * width, (index // 3) * height))
    sheet.save(output / "camera_sweep_contact_sheet.png")
    print(f"wrote {len(images)} candidates and {output / 'camera_sweep_contact_sheet.png'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--mesh-root", type=Path)
    parser.add_argument("--target", nargs=3, type=float, default=[0.0, 0.0, 0.75])
    parser.add_argument("--output", type=Path, default=Path("/tmp/mujoco_camera_sweep"))
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()
    if not args.urdf.is_file():
        parser.error(f"URDF/MJCF not found: {args.urdf}")
    render(args.urdf.resolve(), args.output.resolve(), args.mesh_root, args.target, args.width, args.height)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
