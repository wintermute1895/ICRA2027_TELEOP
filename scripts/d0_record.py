#!/usr/bin/env python3
"""Record one D0 teleoperation episode as a ROS2 bag with a small manifest.

This is the W3 first-stage recorder.  It intentionally records more than the
minimum ACT dataset: master raw teleop, bridge filtered command, mapped command,
error flags, (when requested) the real robot state topics, hand command topics,
and optional camera image topics.  ``--camera-republish`` transparently starts
an image_transport republish process so compressed images are recorded instead
of raw frames.
A later audit script decides whether the recording is complete enough for
``A_action``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


WORKSPACE_ROOT = Path(
    os.environ.get(
        "ARM_TELEOP_WORKSPACE",
        "/home/pao/icra2027_teleop_ws",
    )
)


def _resolve_teleop_config(workspace_root: Path) -> Path:
    """Locate teleop_config.yaml across the layouts this repo has used."""
    explicit = os.environ.get("ARM_TELEOP_CONFIG")
    if explicit:
        return Path(explicit)
    candidates = [
        workspace_root / "lbot_teleop/config/teleop_config.yaml",
        workspace_root / "src/lbot_teleop/config/teleop_config.yaml",
        workspace_root / "install/lbot_teleop/share/lbot_teleop/config/teleop_config.yaml",
        workspace_root / "install/share/lbot_teleop/config/teleop_config.yaml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


TELEOP_CONFIG = _resolve_teleop_config(WORKSPACE_ROOT)
D0_BAG_ROOT = Path(
    os.environ.get(
        "D0_BAG_ROOT",
        "/media/pao/Seagate Hub/ICRA2027_TELEOP_BAGS",
    )
)


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def topics_for(
    arm: str, require_robot_state: bool, robot_namespace: str = "robot1"
) -> list[str]:
    arms = [arm]
    if arm == "both":
        arms = ["left", "right"]

    namespace = robot_namespace.strip("/")
    topics = ["/joint_error_code"]
    for side in arms:
        topics.extend(
            [
                f"/{side}_arm_joint_control",
                f"/vist/{side}/master_joint_raw",
                f"/vist/{side}/master_joint_filtered",
                f"/vist/{side}/mapped_joint_command",
            ]
        )

    if require_robot_state:
        for side in arms:
            topics.extend(
                [
                    f"/{namespace}/{side}_arm/joint_states",
                    f"/{namespace}/{side}_arm/pose_states",
                ]
            )
    return topics


def hand_topics_for(
    arm: str, hand_side: str | None, hand_model: str, robot_namespace: str
) -> list[str]:
    """Return the driver command topic(s) for the hand(s) used in an episode.

    The hand delivery package publishes ``UInt8MultiArray`` commands to the
    lbot driver's ``set_l10_joint`` or ``set_l6_joint`` topic. Recording the
    command stream is the available hand signal because the current driver
    exposes hand setters but no hand-state publisher.
    """
    if hand_side is None:
        sides = ["left", "right"] if arm == "both" else [arm]
    elif hand_side == "both":
        sides = ["left", "right"]
    else:
        sides = [hand_side]
    namespace = robot_namespace.strip("/")
    return [
        f"/{namespace}/{side}_hand/set_{hand_model}_joint"
        for side in sides
    ]


def publisher_count(topic: str) -> int | None:
    """Return the number of live publishers for a topic, or None if absent."""
    try:
        result = subprocess.run(
            ["ros2", "topic", "info", topic],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    match = re.search(r"Publisher count:\s*(\d+)", result.stdout)
    return int(match.group(1)) if match else None


def check_single_publishers(
    topics: list[str], skip: set[str] | None = None
) -> list[str]:
    """Return topics that are missing or have a duplicated publisher."""
    skip = skip or set()
    bad: list[str] = []
    for topic in topics:
        if topic in skip:
            continue
        count = publisher_count(topic)
        if count is None or count == 0:
            bad.append(f"{topic} (no publisher found)")
        elif count > 1:
            bad.append(f"{topic} (Publisher count = {count})")
    return bad


def republish_out_topic(raw_topic: str) -> str:
    base = raw_topic[:-4] if raw_topic.endswith("_raw") else raw_topic
    return f"{base}_repub"


def start_republish(raw_topic: str, log_path: Path):
    out_base = republish_out_topic(raw_topic)
    out_topic = f"{out_base}/compressed"
    format_name = "png" if "depth" in raw_topic else "jpeg"
    log_handle = log_path.open("ab")
    try:
        process = subprocess.Popen(
            [
                "ros2",
                "run",
                "image_transport",
                "republish",
            "raw",
            f"in:={raw_topic}",
            "compressed",
            f"out:={out_base}",
            "--ros-args",
            "-p",
            f"format:={format_name}",
        ],
            stdout=subprocess.DEVNULL,
            stderr=log_handle,
        )
    except FileNotFoundError:
        log_handle.close()
        raise SystemExit(
            "ros2 not found on PATH; source /opt/ros/humble/setup.bash first"
        ) from None
    return process, out_topic, log_handle


def wait_for_publisher(topic: str, timeout_s: float = 15.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        count = publisher_count(topic)
        if count and count > 0:
            return True
        time.sleep(0.5)
    return False


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--arm", choices=("left", "right", "both"), default="right")
    parser.add_argument(
        "--robot-namespace",
        default="robot1",
        help="lbot_driver namespace containing the arm and hand (default: robot1).",
    )
    parser.add_argument(
        "--hand-model",
        choices=("o6", "l6", "l10"),
        default="o6",
        help="Hand model to capture; o6 uses the driver's l6 topic (default: o6).",
    )
    parser.add_argument(
        "--hand-side",
        choices=("left", "right", "both"),
        default=None,
        help="Hand side to capture; defaults to --arm (both for --arm both).",
    )
    parser.add_argument(
        "--hand-topic",
        "--hand-topics",
        action="append",
        default=None,
        metavar="TOPIC",
        help="Override the default hand command topic (repeatable). At least one is required.",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=D0_BAG_ROOT,
        help=f"Episode root directory (default: {D0_BAG_ROOT}).",
    )
    parser.add_argument("--require-robot-state", action="store_true")
    parser.add_argument("--task-id", default="d0-unknown")
    parser.add_argument("--task-description", default="")
    parser.add_argument("--operator", default=os.environ.get("USER", "unknown"))
    parser.add_argument(
        "--external-override",
        choices=("none", "logged", "unlogged"),
        default="logged",
        help="External human/operator override status for this episode.",
    )
    parser.add_argument(
        "--hardware-commands-enabled",
        action="store_true",
        help="Mark the recording as a real-robot armed run; default is dry/preflight.",
    )
    parser.add_argument(
        "--camera-topics",
        action="append",
        default=[],
        metavar="TOPIC",
        help="Image/CameraInfo topic to record (repeatable), e.g. "
        "/camera/color/image_raw/compressed.",
    )
    parser.add_argument(
        "--camera-republish",
        action="append",
        default=[],
        metavar="RAW_TOPIC",
        help="Raw image topic to republish as compressed during recording "
        "(repeatable), e.g. /camera/color/image_raw. The derived compressed "
        "topic is recorded automatically and the republish process is "
        "cleaned up afterwards.",
    )
    parser.add_argument(
        "--camera-preview",
        action="store_true",
        help="Show the color/depth camera view in an OpenCV window while recording.",
    )
    parser.add_argument(
        "--preview-color-topic",
        default="/camera/camera/color/image_raw",
        help="Color topic used by --camera-preview.",
    )
    parser.add_argument(
        "--preview-depth-topic",
        default="/camera/camera/depth/image_rect_raw",
        help="Depth topic used by --camera-preview; pass an empty string to disable.",
    )
    args = parser.parse_args()

    # O6 is represented by the Linker driver as its six-joint (l6) topic.
    hand_topic_model = "l6" if args.hand_model == "o6" else args.hand_model
    hand_topics = list(
        dict.fromkeys(
            args.hand_topic
            or hand_topics_for(
                args.arm, args.hand_side, hand_topic_model, args.robot_namespace
            )
        )
    )
    if not hand_topics:
        parser.error("at least one hand topic is required")

    episode_dir = args.out_root / args.episode_id
    bag_dir = episode_dir / "bag"
    republish: list[tuple[subprocess.Popen, str]] = []
    republish_logs = []
    republish_log = episode_dir / "republish.log"
    keepalive: list[subprocess.Popen] = []
    preview_process: subprocess.Popen | None = None
    try:
        episode_dir.mkdir(parents=True, exist_ok=True)
        raw_topics = list(dict.fromkeys(args.camera_republish))
        for raw_topic in raw_topics:
            if not wait_for_publisher(raw_topic):
                print(f"PREFLIGHT_FAIL\n  {raw_topic} (camera topic not publishing)")
                return 2
        for raw_topic in raw_topics:
            process, out_topic, log_handle = start_republish(raw_topic, republish_log)
            republish.append((process, out_topic))
            republish_logs.append(log_handle)
            print(f"REPUBLISH: {raw_topic} -> {out_topic}", flush=True)
        time.sleep(2)
        for process, out_topic in republish:
            if process.poll() is not None:
                for handle in republish_logs:
                    handle.flush()
                print(
                    f"PREFLIGHT_FAIL\n  {out_topic} "
                    f"(republish process exited, code={process.returncode})"
                )
                if republish_log.is_file():
                    tail = republish_log.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines()[-10:]
                    for line in tail:
                        print(f"  LOG: {line}")
                return 2
        for _, out_topic in republish:
            keepalive.append(
                subprocess.Popen(
                    ["ros2", "topic", "hz", out_topic, "--window", "1"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
        time.sleep(1)

        camera_topics = list(
            dict.fromkeys([*args.camera_topics, *(out for _, out in republish)])
        )
        topics = list(
            dict.fromkeys(
                topics_for(args.arm, args.require_robot_state, args.robot_namespace)
                + hand_topics
                + camera_topics
            )
        )

        explicit_compressed = {
            t for t in args.camera_topics if t.endswith("/compressed")
        }
        bad_topics = check_single_publishers(topics, skip=explicit_compressed)
        if bad_topics:
            print(f"PREFLIGHT_FAIL ({len(bad_topics)} topic(s))")
            for topic in bad_topics:
                print(f"  {topic}")
            print(
                "Fix: make sure teleop and camera are running in the same "
                "isolated ROS environment, start the hand gesture player for "
                "each requested hand topic, kill stale teleop/lbot/linkerta "
                "processes if any, then verify publisher counts and retry."
            )
            return 2

        manifest = {
            "schema": "d0.recording-manifest/v1",
            "episode_id": args.episode_id,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "arm": args.arm,
            "topics": topics,
            "camera_topics": camera_topics,
            "hand_topics": hand_topics,
            "hand_model": args.hand_model,
            "hand_side": args.hand_side or ("both" if args.arm == "both" else args.arm),
            "robot_namespace": args.robot_namespace.strip("/"),
            "require_robot_state": args.require_robot_state,
            "task": {
                "task_id": args.task_id,
                "description": args.task_description,
                "operator": args.operator,
            },
            "external_override": args.external_override,
            "hardware_commands_enabled": args.hardware_commands_enabled,
            "teleop_config_sha256": sha256(TELEOP_CONFIG),
            "teleop_config": str(TELEOP_CONFIG),
            "ros_distro": os.environ.get("ROS_DISTRO", "unknown"),
        }
        write_json(episode_dir / "recording_manifest.json", manifest)

        bag_dir.parent.mkdir(parents=True, exist_ok=True)
        command = ["ros2", "bag", "record", "-o", str(bag_dir), *topics]
        print("RECORDING:", " ".join(command), flush=True)

        if args.camera_preview:
            preview_command = [
                "ros2",
                "run",
                "lbot_demo",
                "d0_camera_preview",
                "--ros-args",
                "-p",
                f"color_topic:={args.preview_color_topic}",
                "-p",
                f"depth_topic:={args.preview_depth_topic}",
            ]
            preview_process = subprocess.Popen(preview_command)
            print("CAMERA_PREVIEW: " + " ".join(preview_command), flush=True)

        started_wall_ns = time.time_ns()
        exit_code: int | None = None
        try:
            result = subprocess.run(command, check=False)
            exit_code = result.returncode
        except KeyboardInterrupt:
            print("RECORDER_INTERRUPTED", flush=True)
        finally:
            finished_wall_ns = time.time_ns()
            finish = {
                "schema": "d0.recording-finished/v1",
                "episode_id": args.episode_id,
                "exit_code": exit_code if exit_code is not None else -2,
                "interrupted": exit_code is None,
                "started_wall_ns": started_wall_ns,
                "finished_wall_ns": finished_wall_ns,
                "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "bag_dir": str(bag_dir),
            }
            write_json(episode_dir / "recording_finished.json", finish)
        print(f"RECORDER_EXIT={exit_code if exit_code is not None else -2}")
        print(f"EPISODE_DIR={episode_dir}")
        return exit_code if exit_code is not None else -2
    finally:
        if preview_process is not None:
            preview_process.terminate()
            try:
                preview_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                preview_process.kill()
        for process, _ in republish:
            process.terminate()
        for process, _ in republish:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        for process in keepalive:
            process.terminate()
        for process in keepalive:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        for handle in republish_logs:
            handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
