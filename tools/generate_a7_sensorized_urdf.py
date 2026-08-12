#!/usr/bin/env python3
"""Attach L10 hands and camera frames to the proven Aug-8 A7 dual-arm URDF."""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = Path("/mnt/F/DexCatch-cx-integretion/models/a7_dual_arm_combined.urdf")
ASSETS = ROOT / "assets/robots/linker_platform"
DEFAULT_LEFT_HAND = ASSETS / "l10/left/linkerhand_l10_left.urdf"
DEFAULT_RIGHT_HAND = ASSETS / "l10/right/linkerhand_l10_right.urdf"
DEFAULT_OUTPUT = ASSETS / "sensorized/a7_dual_arm_l10_hands_cameras.urdf"


def fixed(name: str, parent: str, child: str, xyz: str, rpy: str = "0 0 0") -> ET.Element:
    joint = ET.Element("joint", {"name": name, "type": "fixed"})
    ET.SubElement(joint, "origin", {"xyz": xyz, "rpy": rpy})
    ET.SubElement(joint, "parent", {"link": parent})
    ET.SubElement(joint, "child", {"link": child})
    return joint


def box(name: str, size: str, rgba: str) -> ET.Element:
    link = ET.Element("link", {"name": name})
    inertial = ET.SubElement(link, "inertial")
    ET.SubElement(inertial, "origin", {"xyz": "0 0 0", "rpy": "0 0 0"})
    ET.SubElement(inertial, "mass", {"value": "0.01"})
    ET.SubElement(inertial, "inertia", {"ixx": "1e-6", "ixy": "0", "ixz": "0", "iyy": "1e-6", "iyz": "0", "izz": "1e-6"})
    visual = ET.SubElement(link, "visual")
    geometry = ET.SubElement(visual, "geometry")
    ET.SubElement(geometry, "box", {"size": size})
    material = ET.SubElement(visual, "material", {"name": name + "_material"})
    ET.SubElement(material, "color", {"rgba": rgba})
    return link


def quat_mul(a: list[float], b: list[float]) -> list[float]:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return [aw*bw-ax*bx-ay*by-az*bz, aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx, aw*bz+ax*by-ay*bx+az*bw]


def quat_to_rpy(q: list[float]) -> str:
    w, x, y, z = q
    roll = math.atan2(2*(w*x+y*z), 1-2*(x*x+y*y))
    pitch = math.asin(max(-1.0, min(1.0, 2*(w*y-z*x))))
    yaw = math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
    return f"{roll:.12g} {pitch:.12g} {yaw:.12g}"


def hand_mounts(path: Path | None) -> dict[str, dict[str, list[float]]]:
    result = {side: {"pos": [0.0, 0.0, 0.0], "quat": [1.0, 0.0, 0.0, 0.0]} for side in ("left", "right")}
    if path is None:
        return result
    payload = json.loads(path.read_text(encoding="utf-8"))
    for side in result:
        value = payload.get("hand_mounts", {}).get(side, {})
        if len(value.get("pos", [])) == 3:
            result[side]["pos"] = value["pos"]
        if len(value.get("quat", [])) == 4:
            result[side]["quat"] = value["quat"]
    return result


def add_hand(root: ET.Element, hand_path: Path, side: str, mount: dict[str, list[float]]) -> None:
    hand_root = ET.parse(hand_path).getroot()
    prefix = side.capitalize() + "_Hand_"
    source_links = {item.get("name") for item in hand_root.findall("link")}
    mesh_root = hand_path.parent / "meshes"
    for element in list(hand_root):
        if element.tag not in {"link", "joint"}:
            continue
        item = copy.deepcopy(element)
        item.set("name", prefix + item.get("name", ""))
        for mesh in item.findall(".//mesh"):
            filename = Path(mesh.get("filename", "")).name
            mesh.set("filename", str((mesh_root / filename).resolve()))
        if item.tag == "joint":
            for tag in ("parent", "child", "mimic"):
                node = item.find(tag)
                if node is not None:
                    key = "link" if tag in {"parent", "child"} else "joint"
                    if key == "link" and node.get(key) in source_links:
                        node.set(key, prefix + node.get(key, ""))
                    elif key == "joint":
                        node.set(key, prefix + node.get(key, ""))
        root.append(item)
    wrist = side.capitalize() + "_Wrist_Roll_Link"
    # Calibration is a delta around the known default SDK hand mounting pose.
    final_quat = quat_mul(mount["quat"], [0.0, 0.0, 1.0, 0.0])
    root.append(fixed(side + "_arm_hand_fixed_joint", wrist, prefix + "hand_base_link", " ".join(str(x) for x in mount["pos"]), quat_to_rpy(final_quat)))


def add_camera(root: ET.Element, name: str, parent: str, xyz: str, size: str) -> None:
    mount = name + "_mount_link"
    body = name + "_link"
    optical = name + "_optical_frame"
    root.append(box(mount, "0.05 0.05 0.02", "0.15 0.15 0.15 1"))
    root.append(fixed(name + "_mount_joint", parent, mount, xyz))
    root.append(box(body, size, "0.05 0.35 0.75 1"))
    root.append(fixed(name + "_body_joint", mount, body, "0 0 0.035"))
    root.append(box(optical, "0.006 0.006 0.006", "0.9 0.1 0.1 1",))
    root.append(fixed(name + "_optical_joint", body, optical, "0 0 0", "-1.57079632679 0 -1.57079632679"))


def generate(base: Path, left: Path, right: Path, output: Path, calibration: Path | None = None) -> None:
    root = ET.parse(base).getroot()
    root.set("name", "a7_dual_arm_l10_hands_cameras")
    arm_mesh_root = ASSETS / "combined_robot/meshes/arm"
    for mesh in root.findall(".//mesh"):
        filename = mesh.get("filename", "")
        if "combined_robot/meshes/arm/" in filename:
            mesh.set("filename", str((arm_mesh_root / Path(filename).name).resolve()))
    mounts = hand_mounts(calibration)
    add_hand(root, left, "left", mounts["left"])
    add_hand(root, right, "right", mounts["right"])
    add_camera(root, "head_d435i", "Body_Base_link", "0.18 0 1.55", "0.09 0.025 0.025")
    add_camera(root, "left_wrist_d405", "Left_Wrist_Roll_Link", "0.02 0.04 -0.018", "0.04 0.02 0.02")
    add_camera(root, "right_wrist_d405", "Right_Wrist_Roll_Link", "0.02 -0.04 -0.018", "0.04 0.02 0.02")
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    print(f"generated: {output.resolve()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--left-hand", type=Path, default=DEFAULT_LEFT_HAND)
    parser.add_argument("--right-hand", type=Path, default=DEFAULT_RIGHT_HAND)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--calibration", type=Path, help="JSON emitted by interactive_mujoco_calibration.py")
    args = parser.parse_args()
    for item in (args.base, args.left_hand, args.right_hand):
        if not item.is_file():
            parser.error(f"missing input: {item}")
    if args.calibration is not None and not args.calibration.is_file():
        parser.error(f"missing calibration: {args.calibration}")
    generate(args.base.resolve(), args.left_hand.resolve(), args.right_hand.resolve(), args.output.resolve(), args.calibration.resolve() if args.calibration else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
