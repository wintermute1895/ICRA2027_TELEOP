"""Tests for O6 AccelerationManager with hardware."""

import threading
import time

import pytest

from linkerbot import O6
from linkerbot.hand.o6 import AngleEvent, O6Acceleration, SensorSource
from tests.conftest import InteractiveSession

pytestmark = [pytest.mark.o6, pytest.mark.control]

TOLERANCE = 3.0
MOTION_TIMEOUT_SEC = 10.0
_POLLING_INTERVAL_SEC = 0.1

OPEN = [100.0] * 6
CLOSED = [0.0, 100.0, 0.0, 0.0, 0.0, 0.0]


def _move_and_time(
    hand: O6,
    target: list[float],
    tolerance: float = TOLERANCE,
    timeout_sec: float = MOTION_TIMEOUT_SEC,
) -> tuple[float, bool]:
    """Set target angles, stream until within tolerance, return (elapsed_seconds, timed_out)."""
    timed_out = False
    hand.start_polling({SensorSource.ANGLE: _POLLING_INTERVAL_SEC})
    queue = hand.stream()
    hand.angle.set_angles(target)
    start = time.perf_counter()
    deadline = start + timeout_sec
    timer = threading.Timer(timeout_sec, hand.stop_stream)
    timer.start()

    try:
        for event in queue:
            if not isinstance(event, AngleEvent):
                continue
            angles = event.data.angles
            if all(abs(angles[i] - target[i]) < tolerance for i in range(6)):
                break
            if time.perf_counter() >= deadline:
                print(f"\n  [TIMEOUT] Did not reach target within {timeout_sec:.0f}s")
                timed_out = True
                break
    finally:
        timer.cancel()
        hand.stop_stream()
        hand.stop_polling()

    elapsed = time.perf_counter() - start
    data = hand.angle.get_blocking(timeout_ms=500)
    print(
        f"\n  Motion time: {elapsed:.2f}s | "
        f"Angles: {[f'{a:.1f}' for a in data.angles.to_list()]}"
    )
    return elapsed, timed_out


class TestAccelerationManagerBlocking:
    """Test AccelerationManager blocking read."""

    def test_get_blocking_returns_valid_data(self, o6_hand: O6):
        """Blocking read should return 6 acceleration values, all in [0, 100]."""
        data = o6_hand.acceleration.get_blocking(timeout_ms=500)

        assert data is not None
        assert len(data.accelerations) == 6
        for accel in data.accelerations.to_list():
            assert 0 <= accel <= 100, f"Acceleration {accel} out of range [0, 100]"

    def test_get_blocking_has_timestamp(self, o6_hand: O6):
        """Acceleration data timestamp should be positive and not in the future."""
        data = o6_hand.acceleration.get_blocking(timeout_ms=500)

        assert data.timestamp > 0
        assert data.timestamp <= time.time()


class TestAccelerationManagerSet:
    """Test AccelerationManager set_accelerations method."""

    def test_set_accelerations_with_list(self, o6_hand: O6):
        """set_accelerations should accept a list of floats without error."""
        o6_hand.acceleration.set_accelerations([50.0] * 6)

    def test_set_accelerations_with_o6acceleration(self, o6_hand: O6):
        """set_accelerations should accept an O6Acceleration instance without error."""
        o6_hand.acceleration.set_accelerations(
            O6Acceleration(
                thumb_flex=50.0,
                thumb_abd=50.0,
                index=50.0,
                middle=50.0,
                ring=50.0,
                pinky=50.0,
            )
        )

    def test_set_different_accelerations(self, o6_hand: O6):
        """set_accelerations should accept different per-motor values without error."""
        o6_hand.acceleration.set_accelerations([20.0, 40.0, 60.0, 80.0, 100.0, 50.0])


class TestAccelerationManagerSnapshot:
    """Test AccelerationManager snapshot (cache) mode."""

    def test_snapshot_populated_after_blocking_read(self, o6_hand: O6):
        """get_snapshot should return data after a blocking read."""
        o6_hand.acceleration.get_blocking(timeout_ms=500)

        data = o6_hand.acceleration.get_snapshot()

        assert data is not None
        assert len(data.accelerations) == 6


@pytest.mark.interactive
class TestAccelerationInteractive:
    """Interactive tests for verifying acceleration affects movement ramp-up."""

    def test_acceleration_affects_movement(
        self, o6_hand: O6, interactive_session: InteractiveSession
    ):
        """Verify that acceleration settings visibly affect finger movement ramp-up."""
        session = interactive_session
        motion_results: list[tuple[str, float, bool]] = []

        def track(label: str, target: list[float]) -> None:
            elapsed, timed_out = _move_and_time(o6_hand, target)
            motion_results.append((label, elapsed, timed_out))

        for level, accel_val in [("LOW", 10.0), ("MID", 30.0), ("HIGH", 100.0)]:
            session.step(
                instruction=f"[{level} acceleration={accel_val}] Closing fingers",
                action=lambda lbl=f"{level} close", av=accel_val: (
                    o6_hand.acceleration.set_accelerations([av] * 6),
                    track(lbl, CLOSED),
                ),
                expected=(
                    f"Fingers close with {level} acceleration ramp-up "
                    f"({'gradual start' if level == 'LOW' else 'moderate start' if level == 'MID' else 'sharp immediate start'})"
                ),
            )

            session.step(
                instruction=f"[{level} acceleration={accel_val}] Opening hand",
                action=lambda lbl=f"{level} open": (track(lbl, OPEN),),
                expected="Fingers fully open",
            )

        session.run()

        _move_and_time(o6_hand, OPEN)

        print("\n" + "=" * 52)
        print("  Motion Time Summary")
        print("=" * 52)
        for label, elapsed, timed_out in motion_results:
            timeout_mark = "  [TIMEOUT]" if timed_out else ""
            print(f"  {label:<12}: {elapsed:.2f}s{timeout_mark}")
        print("=" * 52)
        session.save_report()

        if session.quit_early:
            pytest.exit("Tester quit early")

        failed = session.failed_steps()
        if failed:
            pytest.fail(
                f"{len(failed)} step(s) failed: "
                + "; ".join(s.instruction for s in failed)
            )
