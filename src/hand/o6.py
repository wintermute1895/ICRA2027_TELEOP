"""Project-level O6 hand controller.

The vendor ``linkerbot`` package (when installed) is discovered relative to
the repository's ``third_party/`` directory.  This module
is the stable DexCatch-facing seam: gesture definitions and application code
do not need to know where the SDK is installed or how its managers are
organized.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Protocol, Sequence


O6_JOINT_NAMES = (
    "thumb_flex",
    "thumb_abd",
    "index",
    "middle",
    "ring",
    "pinky",
)


class O6HandError(RuntimeError):
    """Raised when the O6 SDK or command contract is unavailable."""


@dataclass(frozen=True)
class O6HandPose:
    """A named O6 pose, using the SDK's normalized ``0..100`` range."""

    name: str
    angles: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.angles) != 6:
            raise ValueError("an O6 pose must contain exactly 6 angles")
        for value in self.angles:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("O6 angles must be numbers")
            if not math.isfinite(float(value)) or not 0 <= float(value) <= 100:
                raise ValueError("O6 angles must be finite and within 0..100")

    def to_list(self) -> list[float]:
        return [float(value) for value in self.angles]


# Useful starting points only.  Applications can replace or add gestures with
# ``register_gesture`` while tuning a particular object or hand.
O6_OPEN = O6HandPose("open", (100, 50, 100, 100, 100, 100))
O6_FIST = O6HandPose("fist", (0, 0, 0, 0, 0, 0))


def load_o6_gestures(path: str | Path) -> dict[str, O6HandPose]:
    """Load named O6 gestures from a portable JSON file.

    The file format is ``{"hand": "O6", "gestures": {"0": [..]}}``.
    Values use the normalized SDK range ``0..100`` and are validated before
    any hardware connection is attempted.
    """
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise O6HandError(f"could not read O6 gesture file: {source}") from exc
    if str(data.get("hand", "")).upper() != "O6":
        raise ValueError(f"gesture file is for {data.get('hand')!r}, not O6")
    raw = data.get("gestures")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("O6 gesture file must contain a non-empty gestures object")
    result: dict[str, O6HandPose] = {}
    for name, values in raw.items():
        if not isinstance(values, (list, tuple)):
            raise ValueError(f"gesture {name!r} must contain a list of six angles")
        pose = O6HandPose(str(name), tuple(values))
        result[pose.name.strip().lower()] = pose
    return result


def save_o6_gestures(path: str | Path, gestures: Mapping[str, O6HandPose]) -> Path:
    """Save O6 gestures as a teammate-portable, human-editable JSON file."""
    if not gestures:
        raise ValueError("at least one O6 gesture is required")
    normalized: dict[str, list[float]] = {}
    for name, pose in gestures.items():
        if not isinstance(pose, O6HandPose):
            raise TypeError("all gestures must be O6HandPose instances")
        normalized[str(name)] = pose.to_list()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"hand": "O6", "gestures": normalized}, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


class O6CommandTransport(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def set_angles(self, angles: Sequence[float]) -> None: ...
    def set_speeds(self, speeds: Sequence[float]) -> None: ...
    def set_torques(self, torques: Sequence[float]) -> None: ...
    def get_angles(self, timeout_ms: float) -> list[float]: ...
    def get_snapshot(self) -> Any: ...


class O6SDKTransport:
    """Adapter around ``linkerbot.hand.o6.O6`` with lazy SDK importing."""

    def __init__(self, *, side: str, interface_name: str, interface_type: str) -> None:
        self.side, self.interface_name, self.interface_type = side, interface_name, interface_type
        self.hand: Any | None = None

    def connect(self) -> None:
        if self.hand is not None:
            return
        try:
            # Make a repository-vendored SDK usable without an editable
            # install when DexCatch is launched from its project root.  The
            # pure-Python hand SDK is vendored in this checkout under
            # ``third_party/linkerbot-python-sdk-main/src``.  Keep the older
            # C/ctypes bundle as a fallback path for installations that still
            # provide a compatible ``linkerbot`` package there.
            repo_root = Path(__file__).resolve().parents[2]
            vendor_roots = (
                repo_root / "third_party" / "linkerbot-python-sdk-main" / "src",
                repo_root / "third_party" / "linkerbot_sdk" / "python",
            )
            for vendor_root in vendor_roots:
                if vendor_root.is_dir() and str(vendor_root) not in sys.path:
                    sys.path.insert(0, str(vendor_root))
            O6 = importlib.import_module("linkerbot.hand.o6").O6
        except ImportError as exc:
            raise O6HandError(
                "linkerbot O6 Python SDK is unavailable. Expected the "
                "repository SDK at third_party/linkerbot-python-sdk-main/src "
                "(or an installed linkerbot-py package); install its Python "
                "dependencies, including python-can, if the import fails"
            ) from exc
        self.hand = O6(
            side=self.side,
            interface_name=self.interface_name,
            interface_type=self.interface_type,
        )

    def disconnect(self) -> None:
        if self.hand is not None:
            self.hand.close()
        self.hand = None

    def _require(self) -> Any:
        if self.hand is None:
            raise O6HandError("O6 hand is not connected")
        return self.hand

    def set_angles(self, angles: Sequence[float]) -> None:
        self._require().angle.set_angles(list(angles))

    def set_speeds(self, speeds: Sequence[float]) -> None:
        self._require().speed.set_speeds(list(speeds))

    def set_torques(self, torques: Sequence[float]) -> None:
        self._require().torque.set_torques(list(torques))

    def get_angles(self, timeout_ms: float) -> list[float]:
        data = self._require().angle.get_blocking(timeout_ms=timeout_ms)
        return [float(value) for value in data.angles.to_list()]

    def get_snapshot(self) -> Any:
        return self._require().get_snapshot()


class O6Hand:
    """Unified O6 interface and extensible named-gesture registry."""

    def __init__(
        self,
        *,
        side: str = "left",
        interface_name: str = "can0",
        interface_type: str = "socketcan",
        transport: O6CommandTransport | None = None,
        gestures: Mapping[str, O6HandPose] | None = None,
    ) -> None:
        selected = side.strip().lower()
        if selected not in {"left", "right"}:
            raise ValueError("side must be 'left' or 'right'")
        self.side = selected
        self.transport = transport or O6SDKTransport(
            side=selected, interface_name=interface_name, interface_type=interface_type
        )
        self.gestures: dict[str, O6HandPose] = {"open": O6_OPEN, "fist": O6_FIST}
        if gestures:
            for pose in gestures.values():
                self.register_gesture(pose)
        self._connected = False

    def connect(self) -> None:
        self.transport.connect()
        self._connected = True

    def disconnect(self) -> None:
        self.transport.disconnect()
        self._connected = False

    def _require_connection(self) -> None:
        if not self._connected:
            raise O6HandError("call connect() before commanding the O6 hand")

    def register_gesture(self, pose: O6HandPose, *, replace: bool = True) -> None:
        if not isinstance(pose, O6HandPose):
            raise TypeError("pose must be an O6HandPose")
        key = pose.name.strip().lower()
        if not key:
            raise ValueError("gesture name must not be empty")
        if not replace and key in self.gestures:
            raise ValueError(f"gesture already exists: {pose.name}")
        self.gestures[key] = pose

    def set_angles(self, angles: Sequence[float]) -> tuple[float, ...]:
        """Set six O6 angles directly in the SDK's native 0..100 range."""
        pose = O6HandPose("runtime", tuple(angles))
        self._require_connection()
        self.transport.set_angles(pose.angles)
        return pose.angles

    def execute_gesture(self, name: str) -> tuple[float, ...]:
        """Execute a registered gesture using the SDK's native 0..100 range."""
        self._require_connection()
        key = name.strip().lower()
        try:
            pose = self.gestures[key]
        except KeyError as exc:
            raise KeyError(f"unknown O6 gesture: {name!r}") from exc
        self.transport.set_angles(pose.angles)
        return pose.angles

    def execute_gesture_number(self, number: int) -> tuple[float, ...]:
        """Execute a numeric gesture such as the recorded ``0``/``1``/``2``/``3``.

        Numeric gesture files are loaded with :meth:`from_gesture_file`; this
        helper keeps the caller in the same 0..100 domain as the O6 SDK.
        """
        if isinstance(number, bool) or not isinstance(number, int):
            raise TypeError("gesture number must be an integer")
        return self.execute_gesture(str(number))

    def set_speed(self, speeds: Sequence[float]) -> tuple[float, ...]:
        pose = O6HandPose("speed", tuple(speeds))
        self._require_connection()
        self.transport.set_speeds(pose.angles)
        return pose.angles

    def set_torque(self, torques: Sequence[float]) -> tuple[float, ...]:
        pose = O6HandPose("torque", tuple(torques))
        self._require_connection()
        self.transport.set_torques(pose.angles)
        return pose.angles

    def get_angles(self, *, timeout_ms: float = 100) -> list[float]:
        self._require_connection()
        if timeout_ms <= 0 or not math.isfinite(timeout_ms):
            raise ValueError("timeout_ms must be finite and positive")
        return self.transport.get_angles(timeout_ms)

    def get_snapshot(self) -> Any:
        self._require_connection()
        return self.transport.get_snapshot()

    @classmethod
    def from_gesture_file(cls, path: str | Path, **kwargs: Any) -> "O6Hand":
        """Construct an O6Hand with gestures loaded from a JSON file."""
        hand = cls(**kwargs)
        hand.gestures = load_o6_gestures(path)
        return hand

    def export_gestures(self, path: str | Path) -> Path:
        """Export the current gesture registry for sharing or versioning."""
        return save_o6_gestures(path, self.gestures)

    def __enter__(self) -> "O6Hand":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()
