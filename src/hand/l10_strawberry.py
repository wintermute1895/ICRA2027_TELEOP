"""Importable ROS2 controller for the calibrated left L10 strawberry grasp.

The controller publishes to the existing LinkerHand ROS2 driver.  It never
opens ``can0`` itself, so the SDK driver remains the single CAN owner.

Typical integration::

    from src.hand import StrawberryL10Hand

    hand = StrawberryL10Hand(hand_type="left")
    hand.connect()
    hand.set_conservative_limits()
    hand.prepare_for_strawberry()
    # The arm controller moves to approach/pregrasp/grasp here.
    hand.grasp_strawberry()
    # The arm controller lifts here.
    hand.release_strawberry()
    hand.disconnect()

Importing, constructing, connecting, and disconnecting do not command motion.
Only the explicitly named command methods publish hand commands.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Optional, Protocol, Sequence


L10_JOINT_NAMES = (
    "thumb_cmc_pitch",
    "thumb_cmc_yaw",
    "index_mcp_pitch",
    "middle_mcp_pitch",
    "ring_mcp_pitch",
    "pinky_mcp_pitch",
    "index_mcp_roll",
    "ring_mcp_roll",
    "pinky_mcp_roll",
    "thumb_cmc_roll",
)


class L10HandError(RuntimeError):
    """Raised when the L10 ROS2 command contract is unavailable or invalid."""


@dataclass(frozen=True)
class L10HandPose:
    """One named L10 command pose in the SDK's integer range (0..255)."""

    name: str
    positions: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.positions) != 10:
            raise ValueError("an L10 pose must contain exactly 10 positions")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in self.positions):
            raise ValueError("L10 positions must be integers")
        if any(value < 0 or value > 255 for value in self.positions):
            raise ValueError("L10 positions must be within 0..255")


# The ready pose was the stable pose immediately before manual tuning.  It is
# open enough for the same strawberry used during calibration.
LEFT_L10_STRAWBERRY_READY = L10HandPose(
    name="strawberry_ready_left_l10",
    positions=(159, 145, 150, 150, 190, 190, 27, 85, 54, 150),
)

# Calibrated on the physical left L10 hand on 2026-08-12.  This exact vector
# successfully retained the test strawberry.
LEFT_L10_STRAWBERRY_GRASP = L10HandPose(
    name="strawberry_grasp_left_l10",
    positions=(166, 125, 160, 150, 190, 190, 67, 85, 54, 150),
)


class L10CommandTransport(Protocol):
    """Small transport seam that keeps the grasp policy testable offline."""

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def publish_position(self, positions: Sequence[int]) -> None: ...

    def publish_limits(self, speed: int, torque: int) -> None: ...


class L10ROS2Transport:
    """ROS2 topic transport for one LinkerHand L10 driver node."""

    def __init__(
        self,
        *,
        hand_type: str = "left",
        connect_timeout_s: float = 5.0,
        state_timeout_s: float = 1.0,
        node_name: str = "dexcatch_l10_strawberry_hand",
    ) -> None:
        selected_hand = hand_type.strip().lower()
        if selected_hand not in {"left", "right"}:
            raise ValueError("hand_type must be 'left' or 'right'")
        if connect_timeout_s <= 0 or state_timeout_s <= 0:
            raise ValueError("ROS2 timeouts must be positive")
        self.hand_type = selected_hand
        self.connect_timeout_s = float(connect_timeout_s)
        self.state_timeout_s = float(state_timeout_s)
        self.node_name = node_name
        self.node = None
        self.publisher = None
        self._rclpy = None
        self._joint_state_type = None
        self._owns_rclpy = False
        self._last_state: Optional[tuple[float, ...]] = None
        self._last_state_at = 0.0

    @property
    def command_topic(self) -> str:
        return f"/cb_{self.hand_type}_hand_control_cmd"

    @property
    def state_topic(self) -> str:
        return f"/cb_{self.hand_type}_hand_state"

    def _on_state(self, message: object) -> None:
        values = tuple(float(value) for value in getattr(message, "position", ()))
        if len(values) != 10 or not all(math.isfinite(value) for value in values):
            return
        self._last_state = values
        self._last_state_at = time.monotonic()

    def connect(self) -> None:
        if self.node is not None:
            return
        try:
            import rclpy
            from rclpy.node import Node
            from sensor_msgs.msg import JointState
        except ImportError as exc:
            raise L10HandError(
                "ROS2 Python packages are unavailable; run inside the Humble environment"
            ) from exc

        try:
            self._owns_rclpy = not rclpy.ok()
            if self._owns_rclpy:
                rclpy.init()
            self._rclpy = rclpy
            self._joint_state_type = JointState
            self.node = Node(self.node_name)
            self.publisher = self.node.create_publisher(
                JointState, self.command_topic, 10
            )
            self.node.create_subscription(
                JointState, self.state_topic, self._on_state, 10
            )
            deadline = time.monotonic() + self.connect_timeout_s
            while time.monotonic() < deadline:
                rclpy.spin_once(self.node, timeout_sec=0.05)
                state_is_fresh = (
                    self._last_state is not None
                    and time.monotonic() - self._last_state_at <= self.state_timeout_s
                )
                if self.publisher.get_subscription_count() > 0 and state_is_fresh:
                    return
            raise L10HandError(
                f"L10 ROS2 driver is not ready: command={self.command_topic}, "
                f"state={self.state_topic}"
            )
        except Exception:
            self.disconnect()
            raise

    def disconnect(self) -> None:
        if self.node is not None:
            self.node.destroy_node()
        self.node = None
        self.publisher = None
        self._last_state = None
        if self._owns_rclpy and self._rclpy is not None and self._rclpy.ok():
            self._rclpy.shutdown()
        self._owns_rclpy = False

    def _require_connection(self) -> None:
        if self.node is None or self.publisher is None or self._joint_state_type is None:
            raise L10HandError("L10 hand is not connected")
        if self.publisher.get_subscription_count() < 1:
            raise L10HandError(f"no ROS2 subscriber on {self.command_topic}")

    def publish_position(self, positions: Sequence[int]) -> None:
        pose = L10HandPose("runtime_command", tuple(positions))
        self._require_connection()
        message = self._joint_state_type()
        message.name = list(L10_JOINT_NAMES)
        message.position = [float(value) for value in pose.positions]
        self.publisher.publish(message)

    def publish_limits(self, speed: int, torque: int) -> None:
        for value, name in ((speed, "speed"), (torque, "torque")):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
                raise ValueError(f"{name} must be an integer within 0..255")
        self._require_connection()
        message = self._joint_state_type()
        # The L10 SDK accepts one value per finger for speed and torque.
        message.velocity = [float(speed)] * 5
        message.effort = [float(torque)] * 5
        self.publisher.publish(message)


class StrawberryL10Hand:
    """High-level hand actions called by the arm-side grasp entry script."""

    def __init__(
        self,
        *,
        hand_type: str = "left",
        transport: Optional[L10CommandTransport] = None,
        ready_pose: L10HandPose = LEFT_L10_STRAWBERRY_READY,
        grasp_pose: L10HandPose = LEFT_L10_STRAWBERRY_GRASP,
    ) -> None:
        if hand_type.strip().lower() != "left" and transport is None:
            raise ValueError(
                "the calibrated strawberry profile currently supports only the left L10"
            )
        self.hand_type = hand_type.strip().lower()
        self.transport = transport or L10ROS2Transport(hand_type=self.hand_type)
        self.ready_pose = ready_pose
        self.grasp_pose = grasp_pose
        self._connected = False

    def connect(self) -> None:
        """Connect to ROS2 and verify fresh L10 state; sends no command."""
        self.transport.connect()
        self._connected = True

    def disconnect(self) -> None:
        """Release ROS2 resources; sends no command."""
        self.transport.disconnect()
        self._connected = False

    def _command(self, pose: L10HandPose) -> tuple[int, ...]:
        if not self._connected:
            raise L10HandError("call connect() before commanding the L10 hand")
        self.transport.publish_position(pose.positions)
        return pose.positions

    def set_conservative_limits(self, *, speed: int = 40, torque: int = 40) -> None:
        """Set the low speed/torque values used during physical calibration."""
        if not self._connected:
            raise L10HandError("call connect() before setting L10 limits")
        self.transport.publish_limits(speed, torque)

    def prepare_for_strawberry(self) -> tuple[int, ...]:
        """Open to the calibrated ready pose before the arm approaches."""
        return self._command(self.ready_pose)

    def grasp_strawberry(self) -> tuple[int, ...]:
        """Close to the physically calibrated strawberry-retention pose."""
        return self._command(self.grasp_pose)

    def release_strawberry(self) -> tuple[int, ...]:
        """Return to the ready pose to release the fruit."""
        return self._command(self.ready_pose)

    def run_hand_only_cycle(self, *, settle_time_s: float = 1.0) -> None:
        """Bench-only ready/close/release cycle; the caller owns workspace safety."""
        if settle_time_s < 0 or not math.isfinite(settle_time_s):
            raise ValueError("settle_time_s must be finite and non-negative")
        self.prepare_for_strawberry()
        time.sleep(settle_time_s)
        self.grasp_strawberry()
        time.sleep(settle_time_s)
        self.release_strawberry()

    def __enter__(self) -> "StrawberryL10Hand":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()
