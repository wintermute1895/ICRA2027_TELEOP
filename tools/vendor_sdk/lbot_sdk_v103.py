"""Minimal ctypes binding for the official LBot SDK 1.0.3 handle ABI.

Only the calls required by the joint-direction checker are exposed. This is a
diagnostic ABI wrapper, not a runtime teleoperation backend; runtime control
uses the ROS2 C++ driver.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path
import platform
import threading
import time


class LbotHandle(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint64)]


class LbotPosition(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double), ("z", ctypes.c_double)]


class LbotEuler(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double), ("z", ctypes.c_double)]


class LbotOrientation(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_double), ("y", ctypes.c_double),
        ("z", ctypes.c_double), ("w", ctypes.c_double),
    ]


class LbotArmState(ctypes.Structure):
    _fields_ = [
        ("name", (ctypes.c_char * 32) * 7),
        ("joint_position", ctypes.c_double * 7),
        ("velocity", ctypes.c_double * 7),
        ("effort", ctypes.c_double * 7),
        ("sec", ctypes.c_int32),
        ("nanosec", ctypes.c_uint32),
        ("frame_id", ctypes.c_char * 64),
        ("end_effector_position", LbotPosition),
        ("euler", LbotEuler),
        ("orientation", LbotOrientation),
    ]

    def joints(self) -> list[float]:
        return [float(value) for value in self.joint_position]

    def names(self) -> list[str]:
        return [bytes(value).split(b"\0", 1)[0].decode("utf-8", "replace") for value in self.name]


class LbotFullState(ctypes.Structure):
    _fields_ = [
        ("left_arm", LbotArmState),
        ("right_arm", LbotArmState),
        ("system_timestamp", ctypes.c_uint64),
        ("arm_ip", ctypes.c_char * 16),
    ]


STATE_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.POINTER(LbotFullState))
ERROR_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p)


def default_library(repo_root: Path) -> Path:
    machine = platform.machine().lower()
    arch = "linux_arm64" if machine in ("aarch64", "arm64") else "linux_x64"
    return repo_root / "ros2_ws" / "src" / "lbot_driver" / "lib" / arch / "liblbot_api.so"


@dataclass(frozen=True)
class ControllerInfo:
    robot_model: str
    controller_version: str


class LbotSdk103:
    LEFT = 0
    RIGHT = 1

    def __init__(self, library: Path):
        self.library = Path(library).resolve()
        if not self.library.is_file():
            raise FileNotFoundError(f"LBot SDK library not found: {self.library}")
        self.lib = ctypes.CDLL(str(self.library), mode=ctypes.RTLD_GLOBAL)
        self._declare_prototypes()
        self.handle = LbotHandle(0)
        self._latest_state: LbotFullState | None = None
        self._state_lock = threading.Lock()
        self._state_event = threading.Event()
        self._last_callback_error = ""
        self._state_cb = STATE_CALLBACK(self._on_state)
        self._error_cb = ERROR_CALLBACK(self._on_error)
        self._monitor_started = False

    def _declare_prototypes(self) -> None:
        self.lib.lbot_init.argtypes = [ctypes.c_char_p]
        self.lib.lbot_init.restype = LbotHandle
        self.lib.lbot_cleanup.argtypes = []
        self.lib.lbot_cleanup.restype = None
        self.lib.lbot_get_api_version.argtypes = []
        self.lib.lbot_get_api_version.restype = ctypes.c_char_p
        self.lib.lbot_get_controller_info.argtypes = [
            LbotHandle, ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_char_p)
        ]
        self.lib.lbot_get_controller_info.restype = ctypes.c_bool
        self.lib.lbot_start_state_monitor.argtypes = [STATE_CALLBACK, ERROR_CALLBACK]
        self.lib.lbot_start_state_monitor.restype = ctypes.c_bool
        self.lib.lbot_stop_state_monitor.argtypes = []
        self.lib.lbot_stop_state_monitor.restype = None
        self.lib.lbot_get_current_state.argtypes = [LbotHandle, ctypes.POINTER(LbotFullState)]
        self.lib.lbot_get_current_state.restype = ctypes.c_bool
        self.lib.lbot_move_joint.argtypes = [
            LbotHandle, ctypes.c_int, ctypes.POINTER(ctypes.c_double),
            ctypes.c_double, ctypes.c_double, ctypes.c_bool,
        ]
        self.lib.lbot_move_joint.restype = ctypes.c_bool
        self.lib.lbot_enable_arm.argtypes = [LbotHandle, ctypes.c_int, ctypes.c_bool]
        self.lib.lbot_enable_arm.restype = ctypes.c_bool
        self.lib.lbot_get_last_error.argtypes = [LbotHandle]
        self.lib.lbot_get_last_error.restype = ctypes.c_char_p

    def _on_state(self, state_ptr: ctypes.POINTER(LbotFullState)) -> None:
        if not state_ptr:
            return
        snapshot = LbotFullState()
        ctypes.memmove(ctypes.byref(snapshot), state_ptr, ctypes.sizeof(snapshot))
        with self._state_lock:
            self._latest_state = snapshot
        self._state_event.set()

    def _on_error(self, code: int, message: bytes | None) -> None:
        text = message.decode("utf-8", "replace") if message else "unknown SDK error"
        self._last_callback_error = f"[{code}] {text}"

    def connect(self, host: str, timeout: float = 10.0) -> None:
        self.handle = self.lib.lbot_init(host.encode("utf-8"))
        if self.handle.id <= 0:
            raise RuntimeError(f"SDK connection failed: {self.last_error()}")
        if not self.lib.lbot_start_state_monitor(self._state_cb, self._error_cb):
            error = self.last_error()
            self.lib.lbot_cleanup()
            self.handle = LbotHandle(0)
            raise RuntimeError(f"state monitor failed: {error}")
        self._monitor_started = True
        if not self._state_event.wait(timeout):
            raise TimeoutError(
                f"no robot state received in {timeout:g}s; callback={self._last_callback_error!r}"
            )

    def close(self) -> None:
        if self._monitor_started:
            self.lib.lbot_stop_state_monitor()
            self._monitor_started = False
        if self.handle.id > 0:
            self.lib.lbot_cleanup()
            self.handle = LbotHandle(0)

    def __enter__(self) -> "LbotSdk103":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def state(self) -> LbotFullState:
        if self.handle.id <= 0:
            raise RuntimeError("SDK is not connected")
        state = LbotFullState()
        if not self.lib.lbot_get_current_state(self.handle, ctypes.byref(state)):
            raise RuntimeError(f"get_current_state failed: {self.last_error()}")
        return state

    def wait_for_fresh_state(self, previous_timestamp: int, timeout: float = 2.0) -> LbotFullState:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.state()
            if int(state.system_timestamp) != previous_timestamp:
                return state
            time.sleep(0.02)
        raise TimeoutError("robot state timestamp did not advance")

    def controller_info(self) -> ControllerInfo:
        model = ctypes.c_char_p()
        version = ctypes.c_char_p()
        if not self.lib.lbot_get_controller_info(self.handle, ctypes.byref(model), ctypes.byref(version)):
            raise RuntimeError(f"get_controller_info failed: {self.last_error()}")
        return ControllerInfo(
            model.value.decode("utf-8", "replace") if model.value else "",
            version.value.decode("utf-8", "replace") if version.value else "",
        )

    def api_version(self) -> str:
        value = self.lib.lbot_get_api_version()
        return value.decode("utf-8", "replace") if value else ""

    def enable_arm(self, arm: int, enabled: bool) -> None:
        if not self.lib.lbot_enable_arm(self.handle, arm, enabled):
            raise RuntimeError(f"enable_arm({arm}, {enabled}) failed: {self.last_error()}")

    def move_joint(self, arm: int, joints: list[float], speed: float, accel: float) -> None:
        if len(joints) != 7:
            raise ValueError("move_joint requires exactly seven joints")
        values = (ctypes.c_double * 7)(*map(float, joints))
        if not self.lib.lbot_move_joint(self.handle, arm, values, speed, accel, True):
            raise RuntimeError(f"move_joint failed: {self.last_error()}")

    def last_error(self) -> str:
        if self.handle.id <= 0:
            return self._last_callback_error or "invalid handle"
        value = self.lib.lbot_get_last_error(self.handle)
        return value.decode("utf-8", "replace") if value else self._last_callback_error
