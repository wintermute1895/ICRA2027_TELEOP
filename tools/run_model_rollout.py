#!/usr/bin/env python3
"""Run a model rollout with one process boundary and optional rosbag record.

This orchestrator starts cameras, ACT/filter candidate production, the shared
deployment supervisor, the bridge, and optional recording. It never imports a
vendor SDK and never arms hardware unless all explicit confirmations are
present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


class Rollout:
    def __init__(self, config: dict[str, Any], *, mode: str, real: bool, record_dir: Path | None,
                 config_path: Path | None = None) -> None:
        self.config = config
        self.mode = mode
        self.real = real
        self.record_dir = record_dir
        self.config_path = config_path
        self.processes: list[tuple[str, subprocess.Popen[bytes]]] = []
        self.log_dir = Path(config.get("log_dir", "/tmp/teleop_rollout_logs"))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._status_offsets: dict[str, int] = {}
        self._status_partial: dict[str, str] = {}

    _STATUS_MARKERS = (
        "[ACT] model loaded",
        "[SUPERVISOR]",
        "[BRIDGE]",
        "first valid ACT command",
        "Right follow SDK call",
        "deployment supervisor:",
        "state=WAITING_FOR_MODEL",
        "fallback suppressed",
        "Initial MoveJ",
        "FAILSAFE",
        "outside [",
        "MoveJ service not available",
    )

    def print_status(self) -> None:
        """Forward key startup/diagnostic log lines to the operator console."""
        for label in ("model_deployment", "hardware_teleop", "rosbag"):
            path = self.log_dir / f"{label}.log"
            if not path.is_file():
                continue
            size = path.stat().st_size
            offset = self._status_offsets.get(label, 0)
            if size < offset:
                offset = 0
            if size == offset:
                continue
            with path.open("rb") as handle:
                handle.seek(offset)
                data = handle.read()
            self._status_offsets[label] = size
            text = self._status_partial.pop(label, "") + data.decode("utf-8", errors="replace")
            *lines, tail = text.split("\n")
            if tail:
                self._status_partial[label] = tail
            for line in lines:
                if any(marker in line for marker in self._STATUS_MARKERS):
                    print(f"[{label}] {line.rstrip()}", flush=True)

    def command(self, label: str, args: list[str]) -> subprocess.Popen[bytes]:
        log = (self.log_dir / f"{label}.log").open("ab")
        process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self.processes.append((label, process))
        print(f"[STARTED] {label}: {' '.join(args)}", flush=True)
        return process

    def wait_topic(self, topic: str, timeout_s: float = 30.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if any(line.strip() == topic for line in self.ros2(["topic", "list"])):
                print(f"[READY] topic {topic}", flush=True)
                return
            time.sleep(1.0)
        raise RuntimeError(f"topic did not appear within {timeout_s:g}s: {topic}")

    @staticmethod
    def ros2(args: list[str]) -> list[str]:
        result = subprocess.run(["ros2", *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
        return result.stdout.splitlines()

    def start_camera(self, camera: dict[str, Any]) -> None:
        namespace = str(camera["namespace"]).rstrip("/")
        root, name = namespace.rsplit("/", 1)
        if not root or not name or not str(camera["serial"]).isdigit():
            raise ValueError(f"invalid camera configuration: {camera}")
        self.command(f"camera_{camera['id']}", [
            "ros2", "launch", "realsense2_camera", "rs_launch.py",
            f"camera_namespace:={root.lstrip('/')}", f"camera_name:={name}",
            f"serial_no:=_{camera['serial']}", "enable_sync:=true", "align_depth.enable:=true",
            f"rgb_camera.color_profile:={camera.get('width', 640)},{camera.get('height', 480)},{camera.get('fps', 15)}",
            f"depth_module.depth_profile:={camera.get('width', 640)},{camera.get('height', 480)},{camera.get('fps', 15)}",
        ])

    def start(self) -> None:
        hardware = self.config.get("hardware") or {}
        source = str(self.config.get("source", "teleop"))
        deployment = self.resolve_path(self.config["deployment_config"])
        candidate_args: list[str] = []
        if source == "act":
            candidate = self.resolve_path(self.config["act_config"])
            self.require_enabled(candidate, "ACT")
            candidate_args += [f"--act-config={candidate}"]
        elif source == "filter":
            candidate = self.resolve_path(self.config["filter_config"])
            self.require_enabled(candidate, "filter")
            candidate_args += [f"--filter-config={candidate}"]
        elif source != "teleop":
            raise ValueError(f"unsupported rollout source: {source}")
        self.require_enabled(deployment, "model deployment")
        for camera in self.config.get("cameras", []):
            self.start_camera(camera)
        for camera in self.config.get("cameras", []):
            self.wait_topic(f"{str(camera['namespace']).rstrip('/')}/color/image_raw")
        deployment_cmd = ["bash", str(ROOT / "scripts/start_model_deployment.sh"), str(deployment), f"--source={source}", f"--{self.mode}", *candidate_args]
        if self.mode == "active":
            deployment_cmd += ["--confirm=I_UNDERSTAND_MODEL_DEPLOYMENT"]
        self.command("model_deployment", deployment_cmd)
        bridge_cmd = [
            "ros2", "launch", "teleop_control_bridge", "hardware_teleop.launch.py",
            f"launch_driver:={'true' if hardware.get('launch_driver', True) else 'false'}",
            f"launch_linkerta:={'true' if hardware.get('launch_linkerta', True) else 'false'}",
            f"armed:={'true' if self.real else 'false'}",
            f"enable_left_arm:={'true' if hardware.get('enable_left_arm', False) else 'false'}",
            f"enable_right_arm:={'true' if hardware.get('enable_right_arm', True) else 'false'}",
            f"master_left_topic:={hardware.get('master_left_topic', '/left_arm_joint_control')}",
            f"master_right_topic:={hardware.get('master_right_topic', '/model_deployment/right_arm_joint_control')}",
        ]
        # Right-arm startup-mode passthrough. Empty values keep legacy bridge
        # semantics; "required"/"bypass" select the v10 A/B diagnosis paths.
        if hardware.get("initial_movej_mode"):
            bridge_cmd.append(f"initial_movej_mode:={hardware['initial_movej_mode']}")
        first_delta = hardware.get("first_command_max_delta_rad")
        if first_delta is not None:
            bridge_cmd.append(f"first_command_max_delta_rad:={first_delta}")
        measured_age = hardware.get("measured_state_max_age_s")
        if measured_age is not None:
            bridge_cmd.append(f"measured_state_max_age_s:={measured_age}")
        self.command("hardware_teleop", bridge_cmd)
        self.wait_topic("/model_deployment/right_arm_joint_control")
        if self.record_dir is not None:
            self.start_recording()
        print("[READY] rollout is running; press Ctrl-C to stop", flush=True)

    def start_recording(self) -> None:
        if self.record_dir.exists():
            raise RuntimeError(f"refusing to overwrite rollout recording: {self.record_dir}")
        self.record_dir.parent.mkdir(parents=True, exist_ok=True)
        topics = list(dict.fromkeys((self.config.get("recording") or {}).get("topics") or []))
        if not topics:
            raise ValueError("recording enabled but no topics configured")
        command = ["ros2", "bag", "record", "--storage", "sqlite3", "--output", str(self.record_dir)]
        try:
            help_result = subprocess.run(
                ["ros2", "bag", "record", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
            )
            help_text = (help_result.stdout or "") if help_result.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            help_text = ""
        if "--topics" in help_text:
            command.append("--topics")
        command += topics
        self.command("rosbag", command)

    @staticmethod
    def resolve_path(value: str | Path) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (ROOT / path).resolve()

    @staticmethod
    def require_enabled(path: Path, label: str) -> None:
        if not path.is_file():
            raise RuntimeError(f"{label} config not found: {path}")
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if config.get("enabled") is not True:
            raise RuntimeError(f"{label} config must set enabled: true: {path}")

    def stop(self) -> None:
        for label, process in reversed(self.processes):
            if process.poll() is None:
                print(f"[STOP] {label}", flush=True)
                try:
                    os.killpg(process.pid, signal.SIGINT)
                except ProcessLookupError:
                    continue
        deadline = time.monotonic() + 20.0
        for _, process in reversed(self.processes):
            while process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.1)
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        if self.record_dir is not None:
            manifest = self.record_dir.parent / f"{self.record_dir.name}.rollout.json"
            provenance: dict[str, Any] = {}
            if self.config_path and self.config_path.is_file():
                provenance["rollout_config"] = str(self.config_path.resolve())
                provenance["rollout_config_sha256"] = hashlib.sha256(self.config_path.read_bytes()).hexdigest()
            for key in ("act_config", "filter_config", "deployment_config"):
                value = self.config.get(key)
                if value:
                    path = self.resolve_path(value)
                    provenance[key] = str(path)
                    if path.is_file():
                        provenance[f"{key}_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest.write_text(json.dumps({
                "schema": "robot_teleop.rollout/v1",
                "source": self.config.get("source", "teleop"),
                "mode": self.mode,
                "real_hardware_armed": self.real,
                "recording": str(self.record_dir),
                "provenance": provenance,
                "stopped_at": time.time_ns(),
            }, indent=2) + "\n", encoding="utf-8")
            print(f"[SAVED] rollout manifest: {manifest}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/runtime/rollout.yaml")
    parser.add_argument("--source", choices=["teleop", "filter", "act"], help="override rollout source")
    parser.add_argument("--filter-config", type=Path, help="override learned-filter runtime config")
    parser.add_argument("--act-config", type=Path, help="override ACT runtime config")
    parser.add_argument("--shadow", action="store_true")
    parser.add_argument("--active", action="store_true")
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--physical-estop-ready", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--model-confirm", default="")
    parser.add_argument("--record-dir", type=Path)
    args = parser.parse_args()
    config_path = Rollout.resolve_path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if args.source:
        config["source"] = args.source
    if args.filter_config:
        config["filter_config"] = str(args.filter_config)
    if args.act_config:
        config["act_config"] = str(args.act_config)
    if config.get("schema") != "robot_teleop.rollout/v1":
        raise SystemExit("unsupported rollout config schema")
    mode = "active" if args.active else "shadow"
    if args.real and (mode != "active" or not args.physical_estop_ready or args.confirm != "I_UNDERSTAND_REAL_ROLLOUT"):
        raise SystemExit("real rollout requires --active --real --physical-estop-ready --confirm=I_UNDERSTAND_REAL_ROLLOUT")
    if mode == "active" and args.model_confirm not in {"", "I_UNDERSTAND_MODEL_DEPLOYMENT"}:
        raise SystemExit("invalid --model-confirm")
    if mode == "active" and args.model_confirm != "I_UNDERSTAND_MODEL_DEPLOYMENT":
        raise SystemExit("active rollout requires --model-confirm=I_UNDERSTAND_MODEL_DEPLOYMENT")
    record_dir = args.record_dir
    if record_dir is None and (config.get("recording") or {}).get("enabled"):
        root = Rollout.resolve_path((config.get("recording") or {}).get("output_root", "rollouts"))
        record_dir = root / time.strftime("%Y%m%dT%H%M%SZ")
    record_dir = Rollout.resolve_path(record_dir) if record_dir is not None else None
    runner = Rollout(config, mode=mode, real=args.real, record_dir=record_dir, config_path=config_path)
    try:
        runner.start()
        while True:
            dead = [(label, proc.returncode) for label, proc in runner.processes if proc.poll() is not None]
            if dead:
                raise RuntimeError(f"rollout process exited: {dead}")
            runner.print_status()
            time.sleep(1.0)
    except KeyboardInterrupt:
        return 0
    finally:
        runner.stop()


if __name__ == "__main__":
    raise SystemExit(main())
