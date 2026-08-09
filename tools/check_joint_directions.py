#!/usr/bin/env python3
"""Compare official-SDK joint directions with the full URDF, one joint at a time."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import termios
import time
import tty

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ROBOT_ASSETS = ROOT / "assets/robots/linker_platform"
sys.path.insert(0, str(ROOT / "tools/vendor_sdk"))
from lbot_sdk_v103 import LbotSdk103, default_library

DEFAULT_URDF = ROBOT_ASSETS / "combined_robot/robot.urdf"
ARM_JOINTS = {
    "left": ["Left_Shoulder_Pitch_Joint", "Left_Shoulder_Roll_Joint", "Left_Shoulder_Yaw_Joint", "Left_Elbow_Pitch_Joint", "Left_Wrist_Yaw_Joint", "Left_Wrist_Pitch_Joint", "Left_Wrist_Roll_Joint"],
    "right": ["Right_Shoulder_Pitch_Joint", "Right_Shoulder_Roll_Joint", "Right_Shoulder_Yaw_Joint", "Right_Elbow_Pitch_Joint", "Right_Wrist_Yaw_Joint", "Right_Wrist_Pitch_Joint", "Right_Wrist_Roll_Joint"],
}
SDK_ARMS = {"left": LbotSdk103.LEFT, "right": LbotSdk103.RIGHT}
LIVE_CONFIRMATION = "MOVE_2_DEG_WITH_ESTOP_READY"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_key(prompt: str, allowed: set[str]) -> str:
    if not sys.stdin.isatty():
        raise RuntimeError("interactive live testing requires a TTY")
    print(prompt, end="", flush=True)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            key = sys.stdin.read(1).lower()
            if key == "\x03":
                raise KeyboardInterrupt
            if key in allowed:
                print()
                return key
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


class RobotView:
    def __init__(self, urdf: Path, headless: bool):
        import pinocchio as pin

        self.pin = pin
        self.robot = pin.RobotWrapper.BuildFromURDF(str(urdf), package_dirs=[str(urdf.parent)])
        self.model = self.robot.model
        self.data = self.model.createData()
        self.q = pin.neutral(self.model)
        self.indices: dict[str, int] = {}
        for names in ARM_JOINTS.values():
            for name in names:
                joint_id = self.model.getJointId(name)
                if joint_id == 0 or self.model.joints[joint_id].nq != 1:
                    raise ValueError(f"URDF joint missing or not 1-DoF: {name}")
                self.indices[name] = self.model.joints[joint_id].idx_q
        self.viz = None
        if not headless:
            import meshcat.geometry as geometry
            from pinocchio.visualize import MeshcatVisualizer

            self.viz = MeshcatVisualizer(self.model, self.robot.collision_model, self.robot.visual_model)
            self.viz.initViewer(open=True)
            self.viz.loadViewerModel(rootNodeName="joint_direction_robot")
            self.viz.viewer["joint_direction/active"].set_object(
                geometry.Sphere(0.025), geometry.MeshLambertMaterial(color=0xE53935)
            )
            self.viz.display(self.q)

    def set_arm(self, arm: str, joints: list[float]) -> None:
        values = np.asarray(joints, dtype=float)
        if values.shape != (7,) or not np.isfinite(values).all():
            raise ValueError(f"{arm} state must contain seven finite joints")
        for name, value in zip(ARM_JOINTS[arm], values):
            self.q[self.indices[name]] = value

    def limits(self, name: str) -> tuple[float, float]:
        index = self.indices[name]
        return float(self.model.lowerPositionLimit[index]), float(self.model.upperPositionLimit[index])

    def show(self, active: str | None = None) -> None:
        if not self.viz:
            return
        self.viz.display(self.q)
        if active:
            joint_id = self.model.getJointId(active)
            self.pin.forwardKinematics(self.model, self.data, self.q)
            self.viz.viewer["joint_direction/active"].set_transform(self.data.oMi[joint_id].homogeneous)


def selected_arms(value: str) -> tuple[str, ...]:
    return ("left", "right") if value == "both" else (value,)


def tests_for(value: str) -> list[tuple[str, int, str]]:
    return [(arm, index, ARM_JOINTS[arm][index]) for index in range(7) for arm in selected_arms(value)]


def sdk_arm_state(state, arm: str):
    return state.left_arm if arm == "left" else state.right_arm


def sync_view(view: RobotView, state, active: str | None = None) -> None:
    view.set_arm("left", sdk_arm_state(state, "left").joints())
    view.set_arm("right", sdk_arm_state(state, "right").joints())
    view.show(active)


def validate_sdk_state(state) -> None:
    for arm in ("left", "right"):
        actual = sdk_arm_state(state, arm).names()
        if actual != ARM_JOINTS[arm]:
            raise RuntimeError(f"{arm} SDK joint order mismatch: {actual} != {ARM_JOINTS[arm]}")
        joints = np.asarray(sdk_arm_state(state, arm).joints())
        if joints.shape != (7,) or not np.isfinite(joints).all():
            raise RuntimeError(f"{arm} SDK state is invalid")


def new_report(args) -> dict[str, object]:
    return {
        "schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(), "live": args.live, "ip": args.ip if args.live else None,
        "arms": args.arms, "step_deg": args.step_deg, "speed_rad_s": args.speed,
        "accel_rad_s2": args.accel, "urdf": str(args.urdf.resolve()),
        "urdf_sha256": sha256(args.urdf), "sdk_library": str(args.sdk_library.resolve()),
        "sdk_library_sha256": sha256(args.sdk_library), "tests": [], "completed": False,
    }


def write_report(report: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"Report: {output}")


def run_offline(args, view: RobotView, report: dict[str, object]) -> int:
    step = math.radians(args.step_deg)
    for arm, index, name in tests_for(args.arms):
        baseline = np.zeros(7)
        view.set_arm(arm, baseline.tolist())
        target = baseline.copy(); target[index] += step
        view.set_arm(arm, target.tolist()); view.show(name)
        lower, upper = view.limits(name)
        report["tests"].append({"arm": arm, "joint_index": index, "joint_name": name, "urdf_lower_rad": lower, "urdf_upper_rad": upper, "offline_preview": True})
        time.sleep(args.preview_seconds)
        view.set_arm(arm, baseline.tolist())
    report["completed"] = True
    print(f"Offline preview PASS: {len(report['tests'])} joints")
    return 0


def run_live(args, view: RobotView, report: dict[str, object]) -> int:
    step, margin = math.radians(args.step_deg), math.radians(args.margin_deg)
    sdk = LbotSdk103(args.sdk_library)
    enabled: list[str] = []
    try:
        sdk.connect(args.ip, args.connect_timeout)
        api_version = sdk.api_version()
        report["sdk_api_version"] = api_version
        if not api_version.startswith("1.0.3"):
            raise RuntimeError(f"expected official SDK API 1.0.3, got {api_version!r}")
        info = sdk.controller_info()
        report["controller"] = {"robot_model": info.robot_model, "controller_version": info.controller_version}
        if "73" not in info.robot_model:
            raise RuntimeError(f"unexpected robot model: {info.robot_model!r}")
        initial = sdk.state(); validate_sdk_state(initial)
        sdk.wait_for_fresh_state(int(initial.system_timestamp)); sync_view(view, initial)
        print("SDK 1.0.3 has no enable-state getter; explicitly setting enable=true and checking return.")
        for arm in selected_arms(args.arms):
            sdk.enable_arm(SDK_ARMS[arm], True); enabled.append(arm)
            print(f"[PASS] {arm} enable command accepted")

        aborted = False
        for arm, index, name in tests_for(args.arms):
            before_state = sdk.state(); validate_sdk_state(before_state)
            before = sdk_arm_state(before_state, arm).joints()
            lower, upper = view.limits(name)
            target = list(before); target[index] += step
            item = {"arm": arm, "joint_index": index, "joint_name": name, "sdk_joint_names": sdk_arm_state(before_state, arm).names(), "before_rad": before, "target_rad": target, "urdf_lower_rad": lower, "urdf_upper_rad": upper, "result": "not_run"}
            report["tests"].append(item)
            if before[index] < lower + margin or target[index] > upper - margin:
                item["result"] = "unsafe_margin"
                raise RuntimeError(f"{arm} J{index + 1} is too close to a URDF limit")

            sync_view(view, before_state, name); view.set_arm(arm, target); view.show(name)
            print(f"\n{arm.upper()} J{index + 1}: {name}; current={math.degrees(before[index]):.2f} deg; preview=+{args.step_deg:.2f} deg")
            key = read_key("[SPACE] move, [s] skip, [q] abort: ", {" ", "s", "q"})
            if key == "q": item["result"] = "aborted"; aborted = True; break
            if key == "s": item["result"] = "skipped"; sync_view(view, before_state); continue

            moved = False
            last_timestamp = int(before_state.system_timestamp)
            next_key = " "
            try:
                sdk.move_joint(SDK_ARMS[arm], target, args.speed, args.accel)
                moved = True
                after_state = sdk.wait_for_fresh_state(last_timestamp)
                last_timestamp = int(after_state.system_timestamp)
                after = sdk_arm_state(after_state, arm).joints(); delta = after[index] - before[index]
                item["after_rad"], item["measured_delta_rad"] = after, delta
                if delta < step * 0.25:
                    item["result"] = "sdk_motion_not_observed"
                    raise RuntimeError(f"{arm} J{index + 1} measured delta is only {math.degrees(delta):.3f} deg")
                sync_view(view, after_state, name)
                answer = read_key("Physical arm and MeshCat moved in the same positive direction? [y/n/u]: ", {"y", "n", "u"})
                item["operator_observation"] = answer
                item["sdk_to_urdf_sign"] = 1 if answer == "y" else (-1 if answer == "n" else None)
                item["result"] = {"y": "match", "n": "opposite", "u": "unclear"}[answer]
                next_key = read_key("[SPACE] return to start and continue, [q] return and abort: ", {" ", "q"})
            finally:
                if moved:
                    try:
                        sdk.move_joint(SDK_ARMS[arm], before, args.speed, args.accel)
                        returned_state = sdk.wait_for_fresh_state(last_timestamp)
                        returned = sdk_arm_state(returned_state, arm).joints()
                        item["returned_rad"] = returned
                        item["return_error_rad"] = float(np.max(np.abs(np.asarray(returned) - np.asarray(before))))
                        sync_view(view, returned_state)
                    except Exception as return_exc:
                        item["return_error"] = str(return_exc)
                        print(f"CRITICAL: automatic return failed: {return_exc}", file=sys.stderr)
            if item.get("return_error_rad", math.inf) > math.radians(0.5):
                raise RuntimeError(f"{arm} J{index + 1} failed to return within 0.5 deg")
            if next_key == "q": aborted = True; break

        report["completed"] = not aborted and len(report["tests"]) == len(tests_for(args.arms)) and all(item["result"] in ("match", "opposite", "unclear", "skipped") for item in report["tests"])
        return 0 if report["completed"] else 2
    finally:
        report["arms_explicitly_enabled"] = enabled
        report["disabled_on_exit"] = False
        sdk.close()
        print("SDK disconnected. Enable state is intentionally unchanged; use the pendant/approved procedure.")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true"); parser.add_argument("--ip")
    parser.add_argument("--arms", choices=("left", "right", "both"), default="both")
    parser.add_argument("--enable-arms", action="store_true"); parser.add_argument("--confirm", default="")
    parser.add_argument("--step-deg", type=float, default=2.0); parser.add_argument("--speed", type=float, default=0.05)
    parser.add_argument("--accel", type=float, default=0.05); parser.add_argument("--margin-deg", type=float, default=5.0)
    parser.add_argument("--connect-timeout", type=float, default=10.0); parser.add_argument("--preview-seconds", type=float, default=0.75)
    parser.add_argument("--headless", action="store_true"); parser.add_argument("--urdf", type=Path, default=DEFAULT_URDF)
    parser.add_argument("--sdk-library", type=Path, default=default_library(ROOT)); parser.add_argument("--output", type=Path, default=ROOT / "reports/joint_direction_report.json")
    args = parser.parse_args()
    if not args.urdf.is_file() or not args.sdk_library.is_file(): parser.error("URDF or SDK library not found")
    if not 0.2 <= args.step_deg <= 3.0: parser.error("--step-deg must be within [0.2, 3.0]")
    if not 0.01 <= args.speed <= 0.10 or not 0.01 <= args.accel <= 0.10: parser.error("speed/accel must be within [0.01, 0.10]")
    if args.margin_deg < 2.0: parser.error("--margin-deg must be at least 2.0")
    if args.live and (not args.ip or not args.enable_arms or args.confirm != LIVE_CONFIRMATION):
        parser.error(f"live mode requires --ip, --enable-arms and --confirm={LIVE_CONFIRMATION}")
    if args.live and args.headless:
        parser.error("live direction comparison requires MeshCat; --headless is offline-only")
    return args


def main() -> int:
    args = parse_args(); report = new_report(args)
    try:
        view = RobotView(args.urdf, args.headless)
        return run_live(args, view, report) if args.live else run_offline(args, view, report)
    except KeyboardInterrupt:
        report["error"] = "operator_interrupt"; print("\nInterrupted; no further commands.", file=sys.stderr); return 130
    except Exception as exc:
        report["error"] = str(exc); print(f"ERROR: {exc}", file=sys.stderr); return 1
    finally:
        write_report(report, args.output)


if __name__ == "__main__": raise SystemExit(main())
