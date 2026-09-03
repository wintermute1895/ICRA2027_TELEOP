#!/usr/bin/env python3
"""Python supervisor and optional Tkinter GUI for teleop data capture.

This module replaces the fragile tmux orchestration layer in
scripts/start_capture_session.sh.  It keeps the existing capture_episode.py as
the episode owner and only manages process lifecycle:

  * launch lbot_driver / cameras / teleop bridge / hand adapter
  * wait for the same ROS topics the shell launcher required
  * keep per-process logs under <data-root>/system/supervisor/<session>-<ts>/
  * run capture_episode.py as the recorder (direct terminal in CLI mode,
    pseudo-terminal + GUI buttons in GUI mode)
  * stop all ROS subprocesses in reverse launch order on SIGINT/SIGTERM/quit

No safety bypass is performed here: the launcher already validated --real,
--physical-estop-ready and --confirm before exec'ing this program.
"""

from __future__ import annotations

import json
import os
import re
import select
import signal
import subprocess
import sys
import threading
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path


ANSI_RE = re.compile(rb"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_ansi(data: bytes) -> str:
    return ANSI_RE.sub(b"", data).decode("utf-8", errors="replace")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class ManagerConfig:
    """Resolved launcher parameters passed through the environment."""

    def __init__(
        self,
        *,
        root_dir: str,
        run_root: str,
        session: str,
        real: bool,
        left_enabled: bool,
        right_enabled: bool,
        camera_serial: str,
        camera_namespace: str,
        second_camera_serial: str,
        second_camera_namespace: str,
        width: int,
        height: int,
        fps: int,
        preview: bool,
        hand_sdk: bool,
        left_hand_can: str,
        right_hand_can: str,
        left_touch: bool,
        right_touch: bool,
        arms: str,
        capture_mode: str,
        episodes: int,
        duration_s: float,
        experiment_id: str,
        condition_id: str,
        operator_id: str,
        auditor_id: str,
        task_id: str,
        experiment_profile: str,
        experiment_manifest: str,
        system_python: str,
        runevidence_python: str,
        runevidence_bin: str,
        event_publisher_python: str,
        annotation_state: str,
        robot_ip: str,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.run_root = Path(run_root)
        self.session = session
        self.real = real
        self.left_enabled = left_enabled
        self.right_enabled = right_enabled
        self.camera_serial = camera_serial
        self.camera_namespace = camera_namespace.rstrip("/")
        self.second_camera_serial = second_camera_serial
        self.second_camera_namespace = second_camera_namespace.rstrip("/")
        self.width = width
        self.height = height
        self.fps = fps
        self.preview = preview
        self.hand_sdk = hand_sdk
        self.left_hand_can = left_hand_can
        self.right_hand_can = right_hand_can
        self.left_touch = left_touch
        self.right_touch = right_touch
        self.arms = arms
        self.capture_mode = capture_mode
        self.episodes = episodes
        self.duration_s = duration_s
        self.experiment_id = experiment_id
        self.condition_id = condition_id
        self.operator_id = operator_id
        self.auditor_id = auditor_id
        self.task_id = task_id
        self.experiment_profile = experiment_profile
        self.experiment_manifest = experiment_manifest
        self.system_python = system_python
        self.runevidence_python = runevidence_python
        self.runevidence_bin = runevidence_bin
        self.event_publisher_python = event_publisher_python
        self.annotation_state = Path(annotation_state)
        self.robot_ip = robot_ip

    @property
    def camera_namespaces(self) -> str:
        result = self.camera_namespace
        if self.second_camera_serial:
            result += "," + self.second_camera_namespace
        return result

    @classmethod
    def from_env(cls) -> "ManagerConfig | None":
        required = {
            "TELEOP_CAP_ROOT_DIR": "root_dir",
            "TELEOP_CAP_RUN_ROOT": "run_root",
            "TELEOP_CAP_SESSION": "session",
            "TELEOP_CAP_CAMERA_SERIAL": "camera_serial",
            "TELEOP_CAP_CAMERA_NAMESPACE": "camera_namespace",
            "TELEOP_CAP_SYSTEM_PYTHON": "system_python",
            "TELEOP_CAP_RUNEVIDENCE_PYTHON": "runevidence_python",
            "TELEOP_CAP_RUNEVIDENCE_BIN": "runevidence_bin",
        }
        missing = [env_name for env_name in required if not os.environ.get(env_name)]
        if missing:
            print(
                "capture_manager: missing required environment: "
                + ", ".join(sorted(missing)),
                file=sys.stderr,
            )
            return None
        session = os.environ["TELEOP_CAP_SESSION"]
        if not re.fullmatch(r"[A-Za-z0-9._-]+", session):
            print("capture_manager: invalid session name: " + session, file=sys.stderr)
            return None

        def integer(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, str(default)))
            except ValueError:
                return default

        def float_number(name: str, default: float) -> float:
            try:
                return float(os.environ.get(name, str(default)))
            except ValueError:
                return default

        return cls(
            root_dir=os.environ["TELEOP_CAP_ROOT_DIR"],
            run_root=os.environ["TELEOP_CAP_RUN_ROOT"],
            session=session,
            real=env_bool("TELEOP_CAP_REAL"),
            left_enabled=env_bool("TELEOP_CAP_LEFT_ENABLED"),
            right_enabled=env_bool("TELEOP_CAP_RIGHT_ENABLED"),
            camera_serial=os.environ["TELEOP_CAP_CAMERA_SERIAL"],
            camera_namespace=os.environ["TELEOP_CAP_CAMERA_NAMESPACE"],
            second_camera_serial=os.environ.get("TELEOP_CAP_SECOND_CAMERA_SERIAL", ""),
            second_camera_namespace=os.environ.get("TELEOP_CAP_SECOND_CAMERA_NAMESPACE", "/camera2/camera"),
            width=integer("TELEOP_CAP_WIDTH", 640),
            height=integer("TELEOP_CAP_HEIGHT", 480),
            fps=integer("TELEOP_CAP_FPS", 15),
            preview=env_bool("TELEOP_CAP_PREVIEW", True),
            hand_sdk=env_bool("TELEOP_CAP_HAND_SDK"),
            left_hand_can=os.environ.get("TELEOP_CAP_LEFT_HAND_CAN", "can0"),
            right_hand_can=os.environ.get("TELEOP_CAP_RIGHT_HAND_CAN", "can1"),
            left_touch=env_bool("TELEOP_CAP_LEFT_TOUCH"),
            right_touch=env_bool("TELEOP_CAP_RIGHT_TOUCH"),
            arms=os.environ.get("TELEOP_CAP_ARMS", "left,right"),
            capture_mode=os.environ.get("TELEOP_CAP_CAPTURE_MODE", "manual"),
            episodes=integer("TELEOP_CAP_EPISODES", 0),
            duration_s=float_number("TELEOP_CAP_DURATION_S", 30.0),
            experiment_id=os.environ.get("TELEOP_CAP_EXPERIMENT_ID", "unassigned"),
            condition_id=os.environ.get("TELEOP_CAP_CONDITION_ID", "unassigned"),
            operator_id=os.environ.get("TELEOP_CAP_OPERATOR_ID", "anonymous"),
            auditor_id=os.environ.get("TELEOP_CAP_AUDITOR_ID", "auditor_01"),
            task_id=os.environ.get("TELEOP_CAP_TASK_ID", "unspecified"),
            experiment_profile=os.environ.get("TELEOP_CAP_EXPERIMENT_PROFILE", ""),
            experiment_manifest=os.environ.get("TELEOP_CAP_EXPERIMENT_MANIFEST", ""),
            system_python=os.environ["TELEOP_CAP_SYSTEM_PYTHON"],
            runevidence_python=os.environ["TELEOP_CAP_RUNEVIDENCE_PYTHON"],
            runevidence_bin=os.environ["TELEOP_CAP_RUNEVIDENCE_BIN"],
            event_publisher_python=os.environ.get(
                "TELEOP_CAP_EVENT_PUBLISHER_PYTHON", os.environ["TELEOP_CAP_SYSTEM_PYTHON"]
            ),
            annotation_state=os.environ.get(
                "TELEOP_CAP_ANNOTATION_STATE", str(Path(os.environ["TELEOP_CAP_RUN_ROOT"]) / ".annotation_state.json")
            ),
            robot_ip=os.environ.get("TELEOP_CAP_ROBOT_IP", ""),
        )


class Component:
    """One managed background process with its own log file and process group."""

    def __init__(
        self,
        *,
        name: str,
        command: list[str],
        log_path: Path,
        root_dir: Path,
        required: bool = True,
        one_shot: bool = False,
    ) -> None:
        self.name = name
        self.command = command
        self.log_path = log_path
        self.root_dir = root_dir
        self.required = required
        self.one_shot = one_shot
        self.process: subprocess.Popen[bytes] | None = None
        self.log_file = None
        self.started_at: str | None = None
        self.status = "pending"

    def start(self, environment: dict[str, str]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file = open(self.log_path, "ab", buffering=0)
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.DEVNULL,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            env=environment,
            cwd=str(self.root_dir),
            start_new_session=True,
            close_fds=True,
        )
        self.started_at = iso_stamp()
        self.status = "running"

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def close_log(self) -> None:
        if self.log_file is not None:
            with suppress(OSError):
                self.log_file.close()
            self.log_file = None

    def stop(self, timeout_s: float = 8.0) -> None:
        if not self.is_running() or self.process is None:
            self.close_log()
            if self.status == "running":
                self.status = "stopped"
            return
        pid = self.process.pid
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGINT)
        deadline = time.monotonic() + timeout_s
        while self.process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.15)
        if self.process.poll() is None:
            with suppress(ProcessLookupError, PermissionError):
                os.killpg(pid, signal.SIGTERM)
            with suppress(subprocess.TimeoutExpired):
                self.process.wait(timeout=3)
        if self.process.poll() is None:
            with suppress(ProcessLookupError, PermissionError):
                os.killpg(pid, signal.SIGKILL)
            with suppress(subprocess.TimeoutExpired):
                self.process.wait(timeout=2)
        self.status = "stopped"
        self.close_log()


class CaptureSession:
    """Lifecycle manager for the ROS graph and recorder."""

    def __init__(self, config: ManagerConfig, on_event=None) -> None:
        self.config = config
        self.on_event = on_event or (lambda text: None)
        self.stop_requested = threading.Event()
        self.shutting_down = False
        self.components: dict[str, Component] = {}
        self.components_lock = threading.Lock()
        self.recorder_process: subprocess.Popen[bytes] | None = None
        self.state_dir = (
            config.run_root / "system" / "supervisor" / f"{config.session}-{utc_stamp()}"
        )
        self.logs_dir = self.state_dir / "logs"
        self.state_path = self.state_dir / "session_state.json"
        self.marker_path = Path(f"/tmp/teleop_capture_supervisor_{config.session}-{os.getuid()}.json")
        self.state_lock = threading.Lock()
        self.monitor_thread: threading.Thread | None = None
        self._ready = False

    def emit(self, text: str) -> None:
        line = f"[teleop-capture-manager] {text}"
        print(line, flush=True)
        self.on_event(line + "\n")

    def _write_state(self) -> None:
        with self.components_lock:
            components_payload = {
                name: {
                    "status": component.status,
                    "pid": component.process.pid if component.process is not None else None,
                    "log": str(component.log_path),
                    "command": component.command,
                }
                for name, component in self.components.items()
            }
        payload = {
            "schema": "robot_teleop.capture-supervisor/v0.1",
            "session": self.config.session,
            "manager_pid": os.getpid(),
            "real": self.config.real,
            "run_root": str(self.config.run_root),
            "started_at": iso_stamp(),
            "stop_requested": self.stop_requested.is_set(),
            "components": components_payload,
            "recorder_pid": self.recorder_process.pid if self.recorder_process is not None else None,
        }
        with self.state_lock:
            atomic_write_json(self.state_path, payload)
            atomic_write_json(
                self.marker_path,
                {
                    "schema": "robot_teleop.capture-supervisor-locator/v0.1",
                    "session": self.config.session,
                    "state_path": str(self.state_path),
                    "run_root": str(self.config.run_root),
                    "manager_pid": os.getpid(),
                    "updated_at": iso_stamp(),
                },
            )

    def _start_component(
        self,
        name: str,
        command: list[str],
        *,
        required: bool = True,
        one_shot: bool = False,
    ) -> Component:
        self.emit(f"starting {name}: {' '.join(command)}")
        component = Component(
            name=name,
            command=command,
            log_path=self.logs_dir / f"{name}.log",
            root_dir=self.config.root_dir,
            required=required,
            one_shot=one_shot,
        )
        component.start(os.environ.copy())
        with self.components_lock:
            self.components[name] = component
        self._write_state()
        if component.process.poll() is not None:
            raise RuntimeError(f"{name} exited during startup with code {component.process.returncode}")
        return component

    def _check_required_alive(self) -> None:
        with self.components_lock:
            components = list(self.components.values())
        for component in components:
            if component.required and component.is_running() is False:
                code = component.process.returncode if component.process is not None else None
                raise RuntimeError(f"{component.name} stopped unexpectedly (exit={code}); see {component.log_path}")

    def snapshot_components(self) -> dict[str, Component]:
        with self.components_lock:
            return dict(self.components)

    def _wait_for_topic(self, topic: str, timeout_s: int) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline and not self.stop_requested.is_set():
            self._check_required_alive()
            try:
                result = subprocess.run(
                    ["ros2", "topic", "list"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=8,
                    env=os.environ.copy(),
                )
                if result.returncode == 0 and topic in set(result.stdout.splitlines()):
                    self.emit(f"topic ready: {topic}")
                    return True
            except (OSError, subprocess.TimeoutExpired):
                pass
            time.sleep(1)
        return False

    def _wait_for_tactile(self, arm: str, timeout_s: int) -> bool:
        force = f"/cb_{arm}_hand_force"
        matrix = f"/cb_{arm}_hand_matrix_touch"
        mass = f"/cb_{arm}_hand_matrix_touch_mass"
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline and not self.stop_requested.is_set():
            try:
                result = subprocess.run(
                    ["ros2", "topic", "list"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=8,
                    env=os.environ.copy(),
                )
                listed = set(result.stdout.splitlines())
                if force in listed or (matrix in listed and mass in listed):
                    self.emit(f"tactile modality ready for {arm}")
                    return True
            except (OSError, subprocess.TimeoutExpired):
                pass
            time.sleep(1)
        return False

    def _wait_for_live_control_sample(self, topic: str, timeout_s: int) -> bool:
        """Require an actual LinkerTA master-arm JointState sample.

        ros2 topic list alone is not enough: the LinkerTA node respawns forever
        when the master arm does not answer the CAN ping, but a topic can still
        be visible briefly or stale.  Only a live message proves the chain.
        """
        self.emit(f"waiting for live master-arm sample on {topic} (up to {timeout_s}s)...")
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline and not self.stop_requested.is_set():
            try:
                result = subprocess.run(
                    [
                        "ros2",
                        "topic",
                        "echo",
                        "--once",
                        "--field",
                        "position",
                        topic,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=8,
                    env=os.environ.copy(),
                )
                if result.returncode == 0 and result.stdout.strip():
                    self.emit(f"live master-arm sample received on {topic}")
                    return True
            except subprocess.TimeoutExpired:
                pass
            except OSError:
                self.emit("WARN: cannot invoke ros2 topic echo for live sample check")
                return False
            time.sleep(0.5)
        return False

    def _camera_launch(self, camera_namespace: str, serial: str) -> list[str]:
        root = camera_namespace[: camera_namespace.rfind("/")]
        name = camera_namespace.rsplit("/", 1)[-1]
        root_arg = root.lstrip("/")
        profile = f"{self.config.width},{self.config.height},{self.config.fps}"
        return [
            "ros2",
            "launch",
            "realsense2_camera",
            "rs_launch.py",
            f"camera_namespace:={root_arg}",
            f"camera_name:={name}",
            f"serial_no:=_{serial}",
            "enable_sync:=true",
            "align_depth.enable:=true",
            f"rgb_camera.color_profile:={profile}",
            f"depth_module.depth_profile:={profile}",
        ]

    def start_background_components(self) -> bool:
        config = self.config
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.emit(
            "REAL_MODE_ARMED=" + ("true" if config.real else "false")
            + " session=" + config.session
            + " data_root=" + str(config.run_root)
        )
        try:
            # lbot_driver
            self._start_component(
                "driver",
                ["ros2", "launch", "lbot_driver", "lbot_start_driver.launch.py"],
            )
            if config.left_enabled and not self._wait_for_topic("/robot1/left_arm/joint_states", 20):
                raise RuntimeError("left arm joint_states did not appear within 20s")
            if config.right_enabled and not self._wait_for_topic("/robot1/right_arm/joint_states", 20):
                raise RuntimeError("right arm joint_states did not appear within 20s")

            # cameras
            self._start_component(
                "camera",
                self._camera_launch(config.camera_namespace, config.camera_serial),
            )
            if not self._wait_for_topic(f"{config.camera_namespace}/color/image_raw", 30):
                raise RuntimeError(f"{config.camera_namespace}/color/image_raw did not appear")
            if not self._wait_for_topic(f"{config.camera_namespace}/aligned_depth_to_color/image_raw", 30):
                raise RuntimeError(f"{config.camera_namespace}/aligned_depth_to_color/image_raw did not appear")

            if config.second_camera_serial:
                self._start_component(
                    "camera2",
                    self._camera_launch(config.second_camera_namespace, config.second_camera_serial),
                )
                if not self._wait_for_topic(f"{config.second_camera_namespace}/color/image_raw", 30):
                    raise RuntimeError("second camera color image did not appear")
                if not self._wait_for_topic(
                    f"{config.second_camera_namespace}/aligned_depth_to_color/image_raw", 30
                ):
                    raise RuntimeError("second camera aligned depth did not appear")

            # LinkerTA + mapping/safety bridge (driver is already running)
            armed = "true" if config.real else "false"
            self._start_component(
                "teleop",
                [
                    "ros2",
                    "launch",
                    "teleop_control_bridge",
                    "hardware_teleop.launch.py",
                    "launch_driver:=false",
                    f"armed:={armed}",
                    f"enable_left_arm:={'true' if config.left_enabled else 'false'}",
                    f"enable_right_arm:={'true' if config.right_enabled else 'false'}",
                ],
            )
            if config.left_enabled:
                if not self._wait_for_topic("/left_arm_joint_control", 20):
                    raise RuntimeError("/left_arm_joint_control did not appear")
                if not self._wait_for_topic("/teleop/left/mapped_joint_command", 20):
                    raise RuntimeError("/teleop/left/mapped_joint_command did not appear")
            if config.right_enabled:
                if not self._wait_for_topic("/right_arm_joint_control", 20):
                    raise RuntimeError("/right_arm_joint_control did not appear")
                if not self._wait_for_topic("/teleop/right/mapped_joint_command", 20):
                    raise RuntimeError("/teleop/right/mapped_joint_command did not appear")
            if config.real:
                if config.left_enabled and not self._wait_for_live_control_sample("/left_arm_joint_control", 30):
                    raise RuntimeError(
                        "LinkerTA master arm is not publishing /left_arm_joint_control; "
                        "check its log for 'No available devices' and verify the master CAN/power connection"
                    )
                if config.right_enabled and not self._wait_for_live_control_sample("/right_arm_joint_control", 30):
                    raise RuntimeError(
                        "LinkerTA master arm is not publishing /right_arm_joint_control; "
                        "check its log for 'No available devices' and verify the master CAN/power connection"
                    )

            # optional hand adapter (disarmed; never a motion owner)
            if config.hand_sdk:
                self._start_component(
                    "hands",
                    [
                        "ros2",
                        "launch",
                        "hand_adapter",
                        "hand_interface.launch.py",
                        "armed:=false",
                        f"launch_left_sdk:={'true' if config.left_enabled else 'false'}",
                        f"launch_right_sdk:={'true' if config.right_enabled else 'false'}",
                        f"left_can:={config.left_hand_can}",
                        f"right_can:={config.right_hand_can}",
                        f"left_touch:={'true' if config.left_touch else 'false'}",
                        f"right_touch:={'true' if config.right_touch else 'false'}",
                        "initialize_pose:=false",
                        "allow_sdk_commands:=false",
                    ],
                )
                if config.left_enabled and not self._wait_for_topic("/cb_left_hand_state", 20):
                    raise RuntimeError("left hand state did not appear")
                if config.right_enabled and not self._wait_for_topic("/cb_right_hand_state", 20):
                    raise RuntimeError("right hand state did not appear")
                if config.left_touch and not self._wait_for_tactile("left", 20):
                    raise RuntimeError("left tactile modality did not appear")
                if config.right_touch and not self._wait_for_tactile("right", 20):
                    raise RuntimeError("right tactile modality did not appear")

            # One-shot time synchronization diagnostic (not required for startup)
            if self.config.system_python:
                self._start_component(
                    "sync",
                    [
                        config.system_python,
                        str(config.root_dir / "tools/diagnose_time_sync.py"),
                        "--duration-s",
                        "10",
                        "--camera-namespace",
                        config.camera_namespace,
                        "--output",
                        str(config.run_root / "pre_capture_time_sync.json"),
                    ],
                    required=False,
                    one_shot=True,
                )

            # Optional image previews are independent GUI processes; closing them is not fatal.
            if config.preview:
                if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
                    try:
                        prefix = subprocess.run(
                            ["ros2", "pkg", "prefix", "rqt_image_view"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            text=True,
                            check=True,
                            env=os.environ.copy(),
                        ).stdout.strip()
                        executable = str(Path(prefix) / "lib/rqt_image_view/rqt_image_view")
                        self._start_component(
                            "preview_rgb1",
                            [config.system_python, executable, f"{config.camera_namespace}/color/image_raw"],
                            required=False,
                            one_shot=True,
                        )
                        if config.second_camera_serial:
                            self._start_component(
                                "preview_rgb2",
                                [
                                    config.system_python,
                                    executable,
                                    f"{config.second_camera_namespace}/color/image_raw",
                                ],
                                required=False,
                                one_shot=True,
                            )
                    except (OSError, subprocess.CalledProcessError):
                        self.emit("WARN: rqt_image_view preview unavailable; continuing")

            if config.real:
                preflight = [
                    config.system_python,
                    str(config.root_dir / "scripts/preflight.py"),
                    "--mode",
                    "capture",
                    "--source",
                    "real",
                    "--arms",
                    config.arms,
                    "--sample-timeout-s",
                    "5",
                ]
                if config.left_touch or config.right_touch:
                    preflight.append("--require-tactile")
                self.emit("running real capture sample preflight...")
                result = subprocess.run(preflight, env=os.environ.copy())
                if result.returncode != 0:
                    raise RuntimeError("real capture preflight failed")
            else:
                self.emit("safe observation mode: capture sample preflight skipped")

            self._ready = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, name="component-monitor", daemon=True)
            self.monitor_thread.start()
            self._write_state()
            self.emit("capture graph ready; recorder can be started")
            return True
        except Exception as error:
            self.emit(f"startup failed: {error}")
            self.stop()
            return False

    def _monitor_loop(self) -> None:
        while not self.stop_requested.wait(0.6):
            try:
                self._check_required_alive()
            except RuntimeError as error:
                self.emit(f"FAILURE: {error}")
                self.stop_requested.set()
                return
            self._write_state()

    def build_recorder_command(self) -> list[str]:
        config = self.config
        command = [
            config.runevidence_python,
            str(config.root_dir / "tools/capture_episode.py"),
            "--runs-root",
            str(config.run_root),
            "--episodes",
            str(config.episodes),
            "--arms",
            config.arms,
            "--cameras",
            config.camera_namespaces,
            "--experiment-id",
            config.experiment_id,
            "--condition-id",
            config.condition_id,
            "--operator-id",
            config.operator_id,
            "--auditor-id",
            config.auditor_id,
            "--annotation-state",
            str(config.annotation_state),
            "--event-publisher-python",
            config.event_publisher_python,
            "--task-id",
            config.task_id,
            "--camera-profile",
            f"{config.width}x{config.height}x{config.fps}",
        ]
        if config.capture_mode == "timed":
            command += ["--auto-start", "--max-duration", str(config.duration_s)]
        return command

    def recorder_environment(self) -> dict[str, str]:
        config = self.config
        env = os.environ.copy()
        env.update(
            {
                "CAMERA_NAMESPACES": config.camera_namespaces,
                "TELEOP_CAPTURE_DURATION_S": str(config.duration_s),
                "TELEOP_CAPTURE_MODE": config.capture_mode,
                "TELEOP_CAPTURE_EPISODES": str(config.episodes),
                "TELEOP_CAPTURE_ARMS": config.arms,
                "TELEOP_TACTILE_ENABLED": str(config.left_touch or config.right_touch).lower(),
                "TELEOP_HARDWARE_COMMANDS_ENABLED": str(config.real).lower(),
                "TELEOP_EXPERIMENT_ID": config.experiment_id,
                "TELEOP_CONDITION_ID": config.condition_id,
                "TELEOP_OPERATOR_ID": config.operator_id,
                "TELEOP_AUDITOR_ID": config.auditor_id,
                "TELEOP_TASK_ID": config.task_id,
                "TELEOP_EXPERIMENT_PROFILE": config.experiment_profile,
                "TELEOP_EXPERIMENT_MANIFEST": config.experiment_manifest,
                "RUNEVIDENCE_BAG_COMPRESSION_MODE": "file",
                "RUNEVIDENCE_BAG_COMPRESSION_FORMAT": "zstd",
                "RUNEVIDENCE_ROOT": str(config.run_root),
                "RUNEVIDENCE_BIN": config.runevidence_bin,
            }
        )
        return env

    def set_recorder(self, process: subprocess.Popen[bytes]) -> None:
        self.recorder_process = process
        self._write_state()

    def stop(self) -> None:
        if self.shutting_down:
            return
        self.shutting_down = True
        self.stop_requested.set()
        self.emit("stopping ROS graph...")
        with self.components_lock:
            names = list(reversed(list(self.components.keys())))
            components = {name: self.components[name] for name in names}
        for name in names:
            component = components[name]
            self.emit(f"stopping {name} (pid={component.process.pid if component.process else 'n/a'})")
            component.stop()
        with self.components_lock:
            self.components.clear()
        self._write_state()
        self.emit("ROS graph stopped; evidence files were not removed")


def _wait_recorder_state(path: Path, timeout_s: float = 35.0) -> dict:
    deadline = time.monotonic() + timeout_s
    last: dict = {}
    while time.monotonic() < deadline:
        try:
            last = json.loads(path.read_text(encoding="utf-8"))
            return last
        except (OSError, json.JSONDecodeError):
            time.sleep(0.25)
    return last


def _terminate_recorder(recorder: subprocess.Popen[bytes]) -> None:
    if recorder.poll() is not None:
        return
    with suppress(ProcessLookupError):
        recorder.send_signal(signal.SIGINT)
    try:
        recorder.wait(timeout=20)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            recorder.send_signal(signal.SIGTERM)
        try:
            recorder.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                recorder.kill()


def _sample_topic_text(topic: str, field: str | None = None) -> str:
    """Read one message with ros2 topic echo, returning a short human string."""
    command = ["ros2", "topic", "echo", "--once", "--truncate-length", "160"]
    if field:
        command += ["--field", field]
    command.append(topic)
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return "no message (timeout 5s)"
    except OSError as error:
        return f"cannot run ros2: {error}"
    if result.returncode == 0 and result.stdout.strip():
        compact = " ".join(result.stdout.strip().split())
        return compact[:220] or "sample received"
    detail = (result.stderr or result.stdout or "").strip().replace("\n", " | ")
    return f"no data ({detail[:180]})"


def run_headless(config: ManagerConfig) -> int:
    session = CaptureSession(config)
    if not sys.stdin.isatty():
        session.emit("WARN: no TTY on stdin; recorder manual keys must be entered in this terminal")

    def handle_signal(_signum, _frame) -> None:
        session.stop_requested.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if not session.start_background_components():
        return 2
    command = session.build_recorder_command()
    env = session.recorder_environment()
    session.emit("starting recorder: " + " ".join(command))
    recorder = subprocess.Popen(command, env=env, cwd=str(config.root_dir))
    session.set_recorder(recorder)
    try:
        while recorder.poll() is None and not session.stop_requested.is_set():
            time.sleep(0.3)
    finally:
        if recorder.poll() is None:
            session.emit("stopping recorder")
            _terminate_recorder(recorder)
        session.stop()
    if recorder.returncode not in (0, None):
        session.emit(f"recorder exited with code {recorder.returncode}")
        return 3
    return 0


def run_gui(config: ManagerConfig) -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox, scrolledtext
    except ImportError as error:
        print(f"Tkinter is unavailable: {error}", file=sys.stderr)
        return 2

    import queue
    import pty

    class CaptureManagerApp(tk.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.title(f"Teleop Capture Manager - {config.session}")
            self.geometry("1080x700")
            self.protocol("WM_DELETE_WINDOW", self.on_close)

            self.output_queue: queue.Queue[object] = queue.Queue()
            self.session = CaptureSession(
                config,
                on_event=lambda text: self.output_queue.put(("log", text)),
            )
            self.pty_master: int | None = None
            self.recorder: subprocess.Popen[bytes] | None = None
            self.worker: threading.Thread | None = None
            self.stopping = False
            self.topic_status: dict[str, str] = {}
            self.topic_threads: list[threading.Thread] = []

            self._build_ui()
            self.after(200, self._drain_output)
            self.after(500, self._poll)
            self.worker = threading.Thread(target=self._worker, name="capture-supervisor", daemon=True)
            self.worker.start()

        def _build_ui(self) -> None:
            import tkinter as tk
            from tkinter import scrolledtext

            top = tk.Frame(self, padx=8, pady=6)
            top.pack(fill=tk.X)
            mode = "REAL_ARMED" if config.real else "SAFE_OBSERVATION"
            self.info_var = tk.StringVar(
                value=(
                    f"session={config.session}  mode={mode}  "
                    f"arms={config.arms}  data={config.run_root}\n"
                    f"task={config.task_id}  experiment={config.experiment_id}  robot_ip={config.robot_ip}"
                )
            )
            tk.Label(top, textvariable=self.info_var, justify=tk.LEFT, anchor="w").pack(fill=tk.X)

            status_row = tk.Frame(self, padx=8, pady=4)
            status_row.pack(fill=tk.X)
            self.status_var = tk.StringVar(value="starting...")
            self.state_var = tk.StringVar(value="recorder: unknown")
            tk.Label(status_row, textvariable=self.status_var, fg="#b23", anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(status_row, textvariable=self.state_var, anchor="e").pack(side=tk.RIGHT)

            middle = tk.Frame(self)
            middle.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

            left = tk.Frame(middle)
            left.pack(side=tk.LEFT, fill=tk.Y, padx=6)
            tk.Label(left, text="Components").pack(anchor="w")
            self.proc_text = scrolledtext.ScrolledText(left, width=42, height=14, state=tk.DISABLED, font=("monospace", 9))
            self.proc_text.pack(fill=tk.Y, expand=True)

            right = tk.Frame(middle)
            right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tk.Label(right, text="Recorder log (Enter/annotations/audit text can be sent below)").pack(anchor="w")
            self.log_text = scrolledtext.ScrolledText(right, width=90, height=24, state=tk.DISABLED, font=("monospace", 9))
            self.log_text.pack(fill=tk.BOTH, expand=True)

            controls = tk.Frame(self, padx=8, pady=6)
            controls.pack(fill=tk.X)

            self.episode_button = tk.Button(controls, text="开始 Episode", command=self.toggle_episode, width=16)
            self.episode_button.grid(row=0, column=0, padx=2)
            self.audit_skip = tk.Button(controls, text="跳过审计", command=lambda: self.send_audit(None), width=12)
            self.audit_skip.grid(row=0, column=1, padx=2)
            self.audit_ok = tk.Button(controls, text="审计: 成功", command=lambda: self.send_audit(True), width=12)
            self.audit_ok.grid(row=0, column=2, padx=2)
            self.audit_fail = tk.Button(controls, text="审计: 失败", command=lambda: self.send_audit(False), width=12)
            self.audit_fail.grid(row=0, column=3, padx=2)
            self.audit_buttons = (self.audit_skip, self.audit_ok, self.audit_fail)
            self.stop_button = tk.Button(controls, text="安全停止并退出", command=self.request_stop, width=18)
            self.stop_button.grid(row=0, column=7, padx=2)

            annotation_label = tk.Label(controls, text="标注键 1-9/0:")
            annotation_label.grid(row=1, column=0, pady=6, sticky="e")
            self.annotation_buttons: list[tk.Button] = []
            for index, digit in enumerate("0123456789"):
                button = tk.Button(
                    controls,
                    text=digit,
                    width=3,
                    command=lambda key=digit: self.send_annotation(key),
                )
                button.grid(row=1, column=index + 1, padx=1, pady=6)
                self.annotation_buttons.append(button)

            input_row = tk.Frame(self, padx=8, pady=8)
            input_row.pack(fill=tk.X)
            self.input_var = tk.StringVar()
            self.entry = tk.Entry(input_row, textvariable=self.input_var)
            self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entry.bind("<Return>", lambda _event: self.send_input_line())
            tk.Button(input_row, text="发送", command=self.send_input_line).pack(side=tk.LEFT, padx=6)
            tk.Label(
                input_row,
                text="全局键: Enter=开始/结束 Episode, 1-9/0=标注, q=退出 recorder（输入框内不受影响）",
                fg="#555",
            ).pack(side=tk.LEFT, padx=8)
            self.bind_all("<KeyPress>", self._on_global_key)

        def _worker(self) -> None:
            import pty

            try:
                if not self.session.start_background_components():
                    self.output_queue.put(("status", "startup failed"))
                    return
                self._start_topic_monitors()
                command = self.session.build_recorder_command()
                env = self.session.recorder_environment()
                master_fd, slave_fd = pty.openpty()
                self.pty_master = master_fd
                self.output_queue.put(("log", "starting recorder PTY\n"))
                recorder = subprocess.Popen(
                    command,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    env=env,
                    cwd=str(config.root_dir),
                    start_new_session=True,
                    close_fds=True,
                )
                os.close(slave_fd)
                self.recorder = recorder
                self.output_queue.put(("status", f"recorder running (pid={recorder.pid})"))
                self.session.set_recorder(recorder)
                pty_log_path = self.session.logs_dir / "recorder_pty.log"
                pty_log_path.parent.mkdir(parents=True, exist_ok=True)
                pty_log = pty_log_path.open("ab", buffering=0)

                def reader() -> None:
                    assert master_fd is not None
                    while recorder.poll() is None:
                        try:
                            ready, _, _ = select.select([master_fd], [], [], 0.1)
                        except (OSError, ValueError):
                            break
                        if not ready:
                            continue
                        try:
                            data = os.read(master_fd, 4096)
                        except OSError:
                            break
                        if not data:
                            break
                        self.output_queue.put(("log", strip_ansi(data)))
                        pty_log.write(data)
                    self.output_queue.put(("recorder_exit", recorder.returncode))

                reader_thread = threading.Thread(target=reader, name="recorder-pty-reader", daemon=True)
                reader_thread.start()
                try:
                    while recorder.poll() is None and not self.session.stop_requested.is_set():
                        time.sleep(0.3)
                    if recorder.poll() is None:
                        self.session.emit("stopping recorder after component failure/stop request")
                        _terminate_recorder(recorder)
                        self.session.stop()
                finally:
                    reader_thread.join(timeout=2)
                    pty_log.close()
                self.output_queue.put(("recorder_exit", recorder.returncode))
            except Exception as error:
                self.output_queue.put(("status", f"error: {error}"))
                self.session.stop()

        def _drain_output(self) -> None:
            import queue as _queue

            try:
                while True:
                    event = self.output_queue.get_nowait()
                    kind = event[0]
                    payload = event[1:]
                    if kind == "log":
                        self._append_log(payload[0])
                    elif kind == "status":
                        self.status_var.set(payload[0])
                    elif kind == "recorder_exit":
                        self.status_var.set(f"recorder exited (code={payload[0]})")
                    elif kind == "topic":
                        topic, text = payload
                        self.topic_status[topic] = text
                    elif kind == "quit":
                        self.after(100, self.destroy)
                        return
            except _queue.Empty:
                pass
            self.after(150, self._drain_output)

        def _append_log(self, text: str) -> None:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, text)
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

        def send_recorder_text(self, text: str) -> None:
            if self.pty_master is not None:
                with suppress(OSError):
                    os.write(self.pty_master, text.encode())

        def send_input_line(self) -> None:
            text = self.input_var.get()
            if not text.strip():
                self.output_queue.put(("log", "[GUI] 输入框为空，未发送（避免误发空行/跳过审计）\n"))
                return
            self.output_queue.put(("log", f"[GUI] sending terminal text: {text.strip()}\n"))
            self.send_recorder_text(text + "\n")
            self.input_var.set("")

        def toggle_episode(self) -> None:
            state = self._annotation_state()
            if self.recorder is None or self.recorder.poll() is not None or self.pty_master is None:
                self.output_queue.put(("log", "[GUI] recorder is not running; Enter was not sent\n"))
                return
            if state.get("active") is True or state.get("status") == "recording":
                self.output_queue.put(("log", "[GUI] sending Enter to stop current episode\n"))
                self.send_recorder_text("\n")
            elif state.get("status") == "ready":
                self.output_queue.put(("log", "[GUI] sending Enter to start next episode\n"))
                self.send_recorder_text("\n")
            else:
                self.output_queue.put(
                    ("log", f"[GUI] recorder is busy ({state.get('status', 'unknown')}); use audit buttons and wait\n")
                )

        def send_audit(self, success: bool | None) -> None:
            if self.recorder is None or self.recorder.poll() is not None or self.pty_master is None:
                self.output_queue.put(("log", "[GUI] recorder is not running; audit was not sent\n"))
                return
            if success is True:
                self.send_recorder_text("y\ny\n\nn\nn\n")
            elif success is False:
                self.send_recorder_text("y\nn\n\nn\nn\n")
            else:
                self.send_recorder_text("\n")

        def send_annotation(self, digit: str) -> None:
            state = self._annotation_state()
            if self.recorder is None or self.recorder.poll() is not None or self.pty_master is None:
                self.output_queue.put(("log", "[GUI] recorder is not running; annotation was not sent\n"))
                return
            if state.get("active") is not True and state.get("status") != "recording":
                self.output_queue.put(("log", "[GUI] not recording; annotation was not sent\n"))
                return
            self.output_queue.put(("log", f"[GUI] sending annotation key {digit}\n"))
            self.send_recorder_text(digit)

        def _on_global_key(self, event) -> str | None:
            if self.entry is not None and event.widget is self.entry:
                return None
            key = event.keysym
            if key in {"Return", "KP_Enter"}:
                if isinstance(event.widget, tk.Button) or isinstance(event.widget, tk.Entry):
                    return None
                self.toggle_episode()
                return "break"
            if event.char in "0123456789":
                self.send_annotation(event.char)
                return "break"
            if event.char in {"q", "Q"}:
                state = self._annotation_state()
                if state.get("active") is not True and state.get("status") in {"ready", "closed"}:
                    self.output_queue.put(("log", "[GUI] sending q to exit recorder\n"))
                    self.send_recorder_text("q\n")
                    return "break"
            return None

        def _start_topic_monitors(self) -> None:
            monitored: list[tuple[str, str | None]] = []
            for arm in config.arms.split(","):
                arm = arm.strip()
                if arm:
                    monitored.append((f"/{arm}_arm_joint_control", "position"))
                    monitored.append((f"/robot1/{arm}_arm/joint_states", "position"))
                    monitored.append((f"/teleop/{arm}/mapped_joint_command", "position"))
            for namespace in config.camera_namespaces.split(","):
                namespace = namespace.strip().rstrip("/")
                if namespace:
                    monitored.append((f"{namespace}/color/image_raw", "header.stamp.sec"))
            for topic, field in monitored:
                thread = threading.Thread(
                    target=self._topic_monitor_loop,
                    args=(topic, field),
                    name=f"topic-monitor-{topic}",
                    daemon=True,
                )
                thread.start()
                self.topic_threads.append(thread)

        def _topic_monitor_loop(self, topic: str, field: str | None) -> None:
            while not self.session.stop_requested.is_set():
                text = _sample_topic_text(topic, field)
                self.output_queue.put(("topic", topic, text))
                if self.session.stop_requested.wait(2.0):
                    return

        def _annotation_state(self) -> dict:
            try:
                return json.loads(config.annotation_state.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {}

        def _poll(self) -> None:
            state = self._annotation_state()
            status_parts = []
            for name, component in self.session.snapshot_components().items():
                status = component.status
                if component.is_running():
                    status = "running"
                status_parts.append(f"{name}={status}")
            self.proc_text.configure(state=tk.NORMAL)
            self.proc_text.delete("1.0", tk.END)
            self.proc_text.insert(tk.END, "\n".join(status_parts) + "\n")
            if self.topic_status:
                self.proc_text.insert(tk.END, "\n--- topic samples ---\n")
                for topic in sorted(self.topic_status):
                    self.proc_text.insert(tk.END, f"{topic}\n  {self.topic_status[topic]}\n")
            self.proc_text.configure(state=tk.DISABLED)

            recorder_state = state.get("status", "unknown")
            self.state_var.set(f"recorder: {recorder_state}")
            recording = state.get("active") is True or recorder_state == "recording"
            if recording:
                self.episode_button.configure(text="结束 Episode")
                self.episode_button.configure(state=tk.NORMAL)
            elif recorder_state == "ready":
                self.episode_button.configure(text="开始 Episode")
                self.episode_button.configure(state=tk.NORMAL)
            else:
                self.episode_button.configure(text="Episode 控制")
                self.episode_button.configure(state=tk.DISABLED)
            annotation_state = tk.NORMAL if recording else tk.DISABLED
            for button in self.annotation_buttons:
                button.configure(state=annotation_state)
            audit_state = tk.NORMAL if recorder_state == "finalizing" else tk.DISABLED
            for button in self.audit_buttons:
                button.configure(state=audit_state)
            self.after(700, self._poll)

        def request_stop(self, confirmed: bool = False) -> None:
            if self.stopping:
                return
            running = any(component.is_running() for component in self.session.snapshot_components().values())
            if not confirmed and (running or (self.recorder is not None and self.recorder.poll() is None)):
                if not messagebox.askyesno("停止采集", "确定安全停止当前采集会话？"):
                    return
            self.stopping = True
            self.stop_button.configure(state=tk.DISABLED)
            self.status_var.set("safe stop requested; waiting for recorder...")
            threading.Thread(target=self._stop_worker, name="capture-stop", daemon=True).start()

        def _stop_worker(self) -> None:
            recorder = self.recorder
            state_path = config.annotation_state
            if recorder is not None and recorder.poll() is None:
                state = _wait_recorder_state(state_path, 2.0)
                if state.get("active") is True or state.get("status") == "recording":
                    self.send_recorder_text("\n")
                    deadline = time.monotonic() + 45
                    while time.monotonic() < deadline and recorder.poll() is None:
                        current = _wait_recorder_state(state_path, 2.0)
                        if current.get("status") not in ("recording", None):
                            break
                        time.sleep(0.5)
                # Defer any open terminal audit, then quit a ready loop.
                current = _wait_recorder_state(state_path, 2.0)
                if current.get("status") in ("finalizing", None):
                    self.send_recorder_text("\n")
                    time.sleep(1.0)
                current = _wait_recorder_state(state_path, 2.0)
                if current.get("status") in ("ready", "closed", None):
                    self.send_recorder_text("q\n")
                deadline = time.monotonic() + 20
                while recorder.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.3)
                if recorder.poll() is None:
                    _terminate_recorder(recorder)
            self.session.stop()
            self.output_queue.put(("status", "session stopped"))
            self.output_queue.put(("quit", None))

        def on_close(self) -> None:
            if self.recorder is not None and self.recorder.poll() is None and not self.stopping:
                if not messagebox.askyesno("停止采集", "Recorder 仍在运行，确定安全停止整个采集会话？"):
                    return
            self.request_stop(confirmed=True)

    app = CaptureManagerApp()
    def request_stop(_signum=None, _frame=None) -> None:
        with suppress(RuntimeError):
            app.after(0, app.request_stop, True)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    app.mainloop()
    return 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print(__doc__, file=sys.stderr)
        return 0 if len(sys.argv) >= 2 else 2
    config = ManagerConfig.from_env()
    if config is None:
        return 2
    mode = sys.argv[1]
    if mode == "gui":
        return run_gui(config)
    if mode in {"python", "headless", "terminal"}:
        return run_headless(config)
    print(f"unknown manager mode: {mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
