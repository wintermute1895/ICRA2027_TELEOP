#!/usr/bin/env python3
"""Interactive ROS bag recorder.

This is the owner of episode lifetime.  Shell scripts only start ROS nodes and
invoke this program; they do not signal or wait on rosbag processes.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import select
import subprocess
import sys
import time
import termios
import tty
import threading
from contextlib import suppress
from pathlib import Path

try:
    from tools.audit_event_recorder import append_event, event_for_key
    from tools.validate_capture_artifacts import validate as validate_capture_artifacts
except ModuleNotFoundError:
    from audit_event_recorder import append_event, event_for_key
    from validate_capture_artifacts import validate as validate_capture_artifacts


def classify_input(data: bytes) -> str:
    """Map one recorder-owned TTY character to an application action."""
    if not data:
        return "closed"
    key = data.decode("utf-8", errors="ignore").lower()
    if key in {"\n", "\r"}:
        return "stop"
    if key in "0123456789":
        return "annotation"
    return "ignore"


def write_annotation_state(
    path: Path | None,
    *,
    status: str,
    active: bool,
    run_dir: Path | None = None,
) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "robot_teleop.annotation-state/v0.1",
        "status": status,
        "active": active,
        "episode_id": run_dir.name if run_dir is not None else None,
        "run_dir": str(run_dir.resolve()) if run_dir is not None else None,
        "updated_wall_time_ns": time.time_ns(),
        "updated_monotonic_time_ns": time.monotonic_ns(),
    }
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def topics(arms: list[str], cameras: list[str], robot_ns: str, teleop_ns: str) -> list[str]:
    result = [f"{teleop_ns}/events", f"{teleop_ns}/terminal_audit"]
    for arm in arms:
        result += [
            f"/{arm}_arm_joint_control",
            f"{teleop_ns}/{arm}/master_joint_raw",
            f"{teleop_ns}/{arm}/master_joint_filtered",
            f"{teleop_ns}/{arm}/mapped_joint_command",
            f"{robot_ns}/{arm}_arm/joint_states",
            f"{robot_ns}/{arm}_arm/vendor_command",
            f"{robot_ns}/{arm}_arm/pose_states",
            f"{robot_ns}/{arm}_hand/control_cmd",
            f"{robot_ns}/{arm}_hand/joint_states",
            f"{teleop_ns}/{arm}/gripper_state",
            f"{teleop_ns}/{arm}/task_context",
        ]
    for camera in cameras:
        camera = camera.rstrip("/")
        result += [
            f"{camera}/color/image_raw",
            f"{camera}/aligned_depth_to_color/image_raw",
            f"{camera}/color/camera_info",
            f"{camera}/depth/camera_info",
        ]
    result += ["/tf", "/tf_static"]
    return result


def write_capture_manifest(run_dir: Path, args: argparse.Namespace, topic_list: list[str]) -> None:
    arms = list(args.arms)
    arm_topics = lambda suffix: ",".join(f"{args.teleop_ns}/{arm}/{suffix}" for arm in arms)
    robot_topics = lambda suffix: ",".join(f"{args.robot_ns}/{arm}_arm/{suffix}" for arm in arms)
    payload = {
        "schema": "robot_teleop.teleop-capture/v1",
        "episode_schema": "robot_teleop.episode/v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "capture_mode": getattr(args, "capture_mode", "timed" if getattr(args, "auto_start", False) else "manual"),
        "source_domain": args.source_domain,
        "capture_arms": args.arms,
        "camera_namespaces": args.cameras,
        "camera_profile": args.camera_profile,
        "duration_s": args.duration,
        "topics": topic_list,
        "experiment": {
            "experiment_id": args.experiment_id,
            "condition_id": args.condition_id,
            "operator_id": args.operator_id,
            "task_id": args.task_id,
        },
        "tactile": {
            "availability": "unavailable",
            "unavailable_reason": "not_enabled_for_capture",
            "topics_recorded": [],
        },
        "recorded_fields": {
            "robot_joint_state": robot_topics("joint_states"),
            "mapped_joint_command": arm_topics("mapped_joint_command"),
            "master_joint_raw": arm_topics("master_joint_raw"),
            "master_joint_filtered": arm_topics("master_joint_filtered"),
            "camera_rgb": ",".join(f"{c.rstrip('/')}/color/image_raw" for c in args.cameras),
            "camera_depth": ",".join(f"{c.rstrip('/')}/aligned_depth_to_color/image_raw" for c in args.cameras),
            "tf": "/tf,/tf_static",
            "audit_events": f"{args.teleop_ns}/events",
            "gripper_state": {
                "topics": {arm: f"{args.teleop_ns}/{arm}/gripper_state" for arm in arms},
                "encoding": "std_msgs/msg/UInt8",
                "semantics": {"0": "open", "1": "closed"},
                "timestamp_source": "rosbag_receipt_time_for_headerless_message",
                "model_input": "binary_gripper_state",
            },
        },
        "human_annotation": {
            "auditor_id": args.auditor_id,
            "topic": f"{args.teleop_ns}/events",
            "sidecar": "artifacts/audit_events.jsonl",
            "timestamp_fields": ["timestamp_ns", "monotonic_time_ns", "wall_time_ns"],
        },
    }
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts" / "teleop_capture_manifest.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def stop_process(process: subprocess.Popen[bytes], timeout: float = 30.0) -> int:
    if process.poll() is None:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGINT)
        deadline = time.monotonic() + timeout
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.25)
        if process.poll() is None:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
    return process.wait()


def write_terminal_audit(run_dir: Path, args: argparse.Namespace) -> None:
    """Write the contract's one-per-episode terminal audit after the bag closes."""
    path = run_dir / "artifacts" / "terminal_audit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    print("[AUDIT] 输入 y 填写成功/失败；回车或 n 跳过并标记 audit_deferred。", flush=True)
    try:
        choice = input("是否现在填写成功/失败？[y/N]: ").strip().lower()
    except EOFError:
        choice = "n"
    if choice not in {"y", "yes"}:
        success = False
        reason = "audit_deferred"
        safety = False
        override = False
    else:
        while True:
            value = input("任务是否成功？[y/N]: ").strip().lower()
            if value in {"y", "yes"}:
                success = True
                break
            if value in {"", "n", "no"}:
                success = False
                break
        reason = input("终止原因（回车=operator_unspecified）: ").strip() or "operator_unspecified"
        safety = input("是否发生安全事件？[y/N]: ").strip().lower() in {"y", "yes"}
        override = input("是否有未记录外部接管？[y/N]: ").strip().lower() in {"y", "yes"}
    payload = {
        "schema": "robot_teleop.terminal-audit/v0.1",
        "episode_id": run_dir.name,
        "success": success,
        "termination_reason": reason,
        "safety_violation": safety,
        "unlogged_external_override": override,
        "audit_source": "manual_structured",
        "operator_id": args.operator_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_ns": time.time_ns(),
        "monotonic_time_ns": time.monotonic_ns(),
        "evidence_refs": ["artifacts/rosbag2"],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"[AUDIT] 已写入 {path}", flush=True)


def bag_record_command(bag_dir: Path, topic_list: list[str], *, compression_mode: str, compression_format: str) -> list[str]:
    """Build a ros2 bag record command compatible with the installed ROS distro.

    Humble uses positional topics and does not accept --disable-keyboard-controls;
    newer ROS 2 releases added both --topics and --disable-keyboard-controls.
    Detect support from the local help text instead of hard-coding one distro.
    """
    command = ["ros2", "bag", "record"]
    try:
        help_result = subprocess.run(
            ["ros2", "bag", "record", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
        )
        help_text = (help_result.stdout or "") if help_result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        help_text = ""
    if "--disable-keyboard-controls" in help_text:
        command.append("--disable-keyboard-controls")
    command += ["--storage", "sqlite3", "--output", str(bag_dir)]
    if compression_mode != "none":
        command += ["--compression-mode", compression_mode, "--compression-format", compression_format]
    if "--topics" in help_text:
        command.append("--topics")
    command += topic_list
    return command


def record_one(args: argparse.Namespace, run_dir: Path, topic_list: list[str]) -> tuple[bool, float]:
    bag_dir = run_dir / "artifacts" / "rosbag2"
    write_capture_manifest(run_dir, args, topic_list)
    command = bag_record_command(
        bag_dir,
        topic_list,
        compression_mode=args.compression_mode,
        compression_format=args.compression_format,
    )
    print(f"[RECORDING] {len(topic_list)} topics | Enter=stop | 1-9/0=annotate", flush=True)
    if sys.stdin.isatty():
        # Consume any CR/LF still queued by the start key before the stop
        # reader is armed; this prevents an Enter press from doing both.
        with suppress(termios.error):
            termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    label = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["identity"]["label"]
    log_path = run_dir / "logs" / f"{label}.log"
    log = log_path.open("wb")
    event_publisher = None
    process: subprocess.Popen[bytes] | None = None
    try:
        event_publisher = subprocess.Popen(
            [args.event_publisher_python, str(Path(__file__).with_name("audit_event_publisher.py")), "--topic", f"{args.teleop_ns}/events"],
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=log,
        )
        # Fail before opening rosbag if the ROS event bridge cannot initialize.
        time.sleep(0.15)
        if event_publisher.poll() is not None:
            raise OSError(f"audit event publisher exited with status {event_publisher.returncode}")
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        startup_deadline = time.monotonic() + 5.0
        while process.poll() is None and time.monotonic() < startup_deadline:
            if bag_dir.is_dir() and any(bag_dir.iterdir()):
                break
            time.sleep(0.05)
        if process.poll() is not None or not bag_dir.is_dir() or not any(bag_dir.iterdir()):
            raise OSError("rosbag did not create its output within 5 seconds")
    except OSError as error:
        log.write(f"rosbag start failed: {error}\n".encode())
        if process is not None and process.poll() is None:
            # A rosbag process can exist even when its output directory is
            # delayed.  Reap it here so a failed episode cannot keep recording
            # outside the RunEvidence lifecycle or block the next session.
            stop_process(process)
        log.close()
        if event_publisher is not None:
            with suppress(OSError):
                if event_publisher.stdin is not None:
                    event_publisher.stdin.close()
            with suppress(subprocess.TimeoutExpired):
                event_publisher.wait(timeout=2)
        print(f"[FAILED] unable to start rosbag: {error}", flush=True)
        return False, 0.0
    write_annotation_state(args.annotation_state, status="recording", active=True, run_dir=run_dir)
    started = time.monotonic()
    old_tty = None
    keyboard_fd = None
    stop_requested = threading.Event()
    keyboard_failed = threading.Event()
    recording_done = threading.Event()
    annotation_sequence = 0
    correction_active = False
    keyboard = None
    if sys.stdin.isatty():
        keyboard_fd = os.dup(sys.stdin.fileno())
        old_tty = termios.tcgetattr(keyboard_fd)
        tty.setcbreak(keyboard_fd)
        termios.tcflush(keyboard_fd, termios.TCIFLUSH)

        def keyboard_reader() -> None:
            nonlocal annotation_sequence, correction_active
            try:
                while not recording_done.is_set():
                    ready, _, _ = select.select([keyboard_fd], [], [], 0.1)
                    if not ready:
                        continue
                    data = os.read(keyboard_fd, 1)
                    action = classify_input(data)
                    if action in {"closed", "stop"}:
                        stop_requested.set()
                        return
                    if action != "annotation":
                        continue
                    key = data.decode("utf-8", errors="ignore").lower()
                    state = {"active": True, "episode_id": run_dir.name, "run_dir": str(run_dir)}
                    event, correction = event_for_key(
                        key, state, auditor_id=args.auditor_id,
                        sequence=annotation_sequence + 1,
                        correction_active=correction_active,
                        ros_time_ns=time.time_ns(),
                    )
                    if event is None:
                        continue
                    annotation_sequence += 1
                    correction_active = correction
                    append_event(run_dir, event)
                    if event_publisher is not None and event_publisher.stdin is not None:
                        try:
                            event_publisher.stdin.write((json.dumps(event, sort_keys=True) + "\n").encode())
                            event_publisher.stdin.flush()
                        except (BrokenPipeError, OSError):
                            pass
                    print(
                        f"\r\033[K[AUDIT #{annotation_sequence}] {event['event_type']} "
                        f"| timestamp_ns={event['timestamp_ns']}", end="", flush=True,
                    )
            except OSError:
                keyboard_failed.set()

        keyboard = threading.Thread(target=keyboard_reader, name="capture-keyboard", daemon=True)
        keyboard.start()
    last_display = 0.0
    stop_reason = "unknown"
    try:
        while True:
            if process.poll() is not None:
                stop_reason = f"rosbag_exited_unexpectedly:{process.returncode}"
                break
            size = sum(p.stat().st_size for p in bag_dir.glob("*") if p.is_file())
            now = time.monotonic()
            elapsed = int(now - started)
            if now - last_display >= 1.0:
                print(f"\r\033[K[REC {elapsed // 60:02d}:{elapsed % 60:02d}] {size / 1048576:.0f}MB | Enter=stop", end="", flush=True)
                last_display = now
            if stop_requested.is_set():
                stop_reason = "operator_enter"
                break
            if keyboard_failed.is_set():
                stop_reason = "keyboard_read_failed"
                break
            if args.max_duration > 0 and time.monotonic() - started >= args.max_duration:
                print(f"\n[MAX-DURATION] {args.max_duration:.0f}s reached; stopping automatically.", flush=True)
                stop_reason = "max_duration"
                break
            stop_requested.wait(0.02)
    except KeyboardInterrupt:
        stop_reason = "keyboard_interrupt"
    finally:
        recording_done.set()
        if keyboard is not None:
            keyboard.join(timeout=1.0)
        if correction_active:
            state = {"active": True, "episode_id": run_dir.name, "run_dir": str(run_dir)}
            event, correction_active = event_for_key(
                "4", state, auditor_id=args.auditor_id,
                sequence=annotation_sequence + 1,
                correction_active=True, ros_time_ns=time.time_ns(),
            )
            if event is not None:
                event["source"] = "capture_state_machine"
                event["payload"]["auto_closed_at_episode_end"] = True
                append_event(run_dir, event)
                if event_publisher is not None and event_publisher.stdin is not None:
                    with suppress(BrokenPipeError, OSError):
                        event_publisher.stdin.write((json.dumps(event, sort_keys=True) + "\n").encode())
                        event_publisher.stdin.flush()
                print("\n[AUDIT] open correction interval closed at episode end.", flush=True)
        if old_tty is not None:
            with suppress(OSError):
                termios.tcsetattr(keyboard_fd, termios.TCSADRAIN, old_tty)
        if keyboard_fd is not None:
            with suppress(OSError):
                os.close(keyboard_fd)
        if event_publisher is not None:
            with suppress(OSError):
                if event_publisher.stdin is not None:
                    event_publisher.stdin.close()
            with suppress(subprocess.TimeoutExpired):
                event_publisher.wait(timeout=3)
            if event_publisher.poll() is None:
                with suppress(ProcessLookupError):
                    event_publisher.kill()
    print(f"\n[FINALIZING] reason={stop_reason}; stopping rosbag and waiting for metadata...", flush=True)
    write_annotation_state(args.annotation_state, status="finalizing", active=False, run_dir=run_dir)
    code = stop_process(process)
    log.close()
    metadata = bag_dir / "metadata.yaml"
    if not metadata.exists():
        subprocess.run(["ros2", "bag", "reindex", str(bag_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    db_files = list(bag_dir.glob("*.db3")) + list(bag_dir.glob("*.db3.zstd"))
    expected_stop = stop_reason in {"operator_enter", "max_duration", "keyboard_interrupt"}
    ok = metadata.is_file() and bool(db_files) and expected_stop
    if ok:
        print(f"[SAVED] {bag_dir}", flush=True)
    elif not metadata.is_file() or not db_files:
        print("[FAILED] rosbag metadata/database incomplete", flush=True)
    else:
        print(f"[FAILED] recorder stopped unexpectedly: {stop_reason}", flush=True)
    return ok, time.monotonic() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=0)
    parser.add_argument("--arms", default="right")
    parser.add_argument("--cameras", default="/camera/camera,/camera2/camera")
    parser.add_argument("--experiment-id", default="unassigned")
    parser.add_argument("--condition-id", default="unassigned")
    parser.add_argument("--operator-id", default="anonymous")
    parser.add_argument("--auditor-id", default="auditor_01")
    parser.add_argument("--annotation-state", type=Path)
    parser.add_argument("--event-publisher-python", default="/usr/bin/python3")
    parser.add_argument("--task-id", default="unspecified")
    parser.add_argument("--robot-ns", default="/robot1")
    parser.add_argument("--teleop-ns", default="/teleop")
    parser.add_argument("--camera-profile", default="640x480x15")
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--max-duration", type=float, default=300)
    parser.add_argument("--compression-mode", default="file")
    parser.add_argument("--compression-format", default="zstd")
    parser.add_argument("--source-domain", default="real")
    parser.add_argument("--auto-start", action="store_true")
    args = parser.parse_args()
    args.arms = [x for x in args.arms.split(",") if x]
    args.cameras = [x for x in args.cameras.split(",") if x]
    from run_evidence.lifecycle import build_manifest, finish_run, initialize_run, mark_running, new_run_id, write_host_capture
    from run_evidence.report import write_report
    from run_evidence.analysis import write_analysis

    i = 1
    write_annotation_state(args.annotation_state, status="ready", active=False)
    while args.episodes == 0 or i <= args.episodes:
        if args.auto_start:
            print(f"\n========== AUTO START: EPISODE {i} ==========", flush=True)
        else:
            print(
                f"\n========== READY: EPISODE {i} ==========\n"
                "按 Enter 开始本条；输入 q 后回车退出。录制中数字键 1-9/0 可实时标注。",
                flush=True,
            )
            try:
                if input().strip().lower() == "q":
                    break
            except EOFError:
                print("[EXIT] input closed; ending capture session.", flush=True)
                break
        label = f"{args.experiment_id}-{args.condition_id}-episode-{i}"
        run_dir = initialize_run(args.runs_root, new_run_id(label), [sys.argv[0]], label, {
            "experiment_id": args.experiment_id, "condition_id": args.condition_id,
            "operator_id": args.operator_id, "task_id": args.task_id,
        }, domain="robotics")
        mark_running(run_dir); write_host_capture(run_dir, "start", "standard")
        topic_list = topics(args.arms, args.cameras, args.robot_ns, args.teleop_ns)
        try:
            ok, wall_seconds = record_one(args, run_dir, topic_list)
            exit_code = 0 if ok else 3
        except (OSError, KeyboardInterrupt) as error:
            print(f"[FAILED] capture interrupted: {error}", flush=True)
            ok, wall_seconds, exit_code = False, 0.0, 130
        finally:
            write_annotation_state(args.annotation_state, status="finalizing", active=False, run_dir=run_dir)
        if ok:
            write_terminal_audit(run_dir, args)
        capture_failures = validate_capture_artifacts(run_dir, require_terminal_audit=ok)
        validation_path = run_dir / "artifacts" / "capture_validation.json"
        validation_path.write_text(json.dumps({
            "schema": "robot_teleop.capture-artifact-validation/v0.1",
            "passed": not capture_failures,
            "failures": capture_failures,
        }, indent=2) + "\n", encoding="utf-8")
        if capture_failures:
            ok = False
            exit_code = 4
            print(f"[FAILED] capture validation: {', '.join(capture_failures)}", flush=True)
        finish_run(run_dir, exit_code, False, wall_seconds)
        write_host_capture(run_dir, "end", "standard")
        write_report(run_dir); write_analysis(run_dir); build_manifest(run_dir)
        print(f"[EPISODE {i}] {'complete' if ok else 'incomplete'}: {run_dir}", flush=True)
        write_annotation_state(args.annotation_state, status="ready", active=False)
        i += 1
    write_annotation_state(args.annotation_state, status="closed", active=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
