"""Tests for L20Lite SpeedManager with hardware."""

import threading
import time

import pytest

from linkerbot import L20lite
from linkerbot.hand.l20lite import AngleEvent, L20liteSpeed, SensorSource
from tests.conftest import InteractiveSession

pytestmark = [pytest.mark.l20lite, pytest.mark.control]

TOLERANCE = 3.0
MOTION_TIMEOUT_SEC = 20.0
_POLLING_INTERVAL_SEC = 0.4


def _move_and_time(
    hand: L20lite,
    target: list[float],
    tolerance: float = TOLERANCE,
    timeout_sec: float = MOTION_TIMEOUT_SEC,
) -> tuple[float, bool]:
    """Set target angles, stream until within tolerance, return (elapsed_seconds, timed_out)."""

    timed_out = False
    hand.start_polling({SensorSource.ANGLE: _POLLING_INTERVAL_SEC})
    queue = hand.stream()
    hand.angle.set_angles(
        target
    )  # HACK: set_angles after stream() may race with polling
    start = time.perf_counter()

    deadline = start + timeout_sec
    timer = threading.Timer(timeout_sec, hand.stop_stream)
    timer.start()

    try:
        for event in queue:
            if not isinstance(event, AngleEvent):
                continue
            angles = event.data.angles
            if all(abs(angles[i] - target[i]) < tolerance for i in range(10)):
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


class TestSpeedManagerSet:
    """Test SpeedManager set_speeds method."""

    def test_set_speeds_with_list(self, l20lite_hand: L20lite):
        """set_speeds should accept a list of floats without error."""
        l20lite_hand.speed.set_speeds([50.0] * 10)

    def test_set_speeds_with_l20lite_speed(self, l20lite_hand: L20lite):
        """set_speeds should accept an L20liteSpeed instance without error."""
        l20lite_hand.speed.set_speeds(
            L20liteSpeed(
                thumb_flex=50.0,
                thumb_abd=100.0,
                index_flex=50.0,
                middle_flex=50.0,
                ring_flex=50.0,
                pinky_flex=50.0,
                index_abd=50.0,
                ring_abd=50.0,
                pinky_abd=50.0,
                thumb_yaw=100.0,
            )
        )

    def test_set_different_speeds(self, l20lite_hand: L20lite):
        """set_speeds should accept different per-motor speeds without error."""
        l20lite_hand.speed.set_speeds(
            [20.0, 40.0, 60.0, 80.0, 100.0, 50.0, 30.0, 70.0, 90.0, 10.0]
        )


class TestSpeedManagerBlocking:
    """Test SpeedManager blocking read."""

    def test_get_blocking_returns_valid_data(self, l20lite_hand: L20lite):
        """Blocking read should return 10 speed values."""
        data = l20lite_hand.speed.get_blocking(timeout_ms=500)

        assert data is not None
        assert len(data.speeds) == 10
        print(f"\n  Speeds: {[f'{s:.1f}' for s in data.speeds.to_list()]}")

    def test_get_blocking_has_timestamp(self, l20lite_hand: L20lite):
        """Speed data should have a valid timestamp."""
        data = l20lite_hand.speed.get_blocking(timeout_ms=500)

        assert data.timestamp > 0
        assert data.timestamp <= time.time()


class TestSpeedManagerSnapshot:
    """Test SpeedManager snapshot mode."""

    def test_snapshot_populated_after_read(self, l20lite_hand: L20lite):
        """get_snapshot should return non-None after blocking read."""
        l20lite_hand.speed.get_blocking(timeout_ms=500)
        data = l20lite_hand.speed.get_snapshot()
        assert data is not None
        assert len(data.speeds) == 10


@pytest.mark.interactive
class TestSpeedInteractive:
    """Interactive tests for verifying speed affects movement."""

    def test_speed_levels(
        self, l20lite_hand: L20lite, interactive_session: InteractiveSession
    ):
        """Verify low/mid/high speed visibly affects finger movement speed."""
        session = interactive_session
        motion_results: list[tuple[str, float, bool]] = []

        def track(label: str, target: list[float]) -> None:
            elapsed, timed_out = _move_and_time(l20lite_hand, target)
            motion_results.append((label, elapsed, timed_out))

        for level, speed_val in [("LOW", 10.0), ("MID", 30.0), ("HIGH", 100.0)]:
            # Close fingers
            session.step(
                instruction=f"[{level} speed={speed_val}] Closing fingers",
                action=lambda lbl=f"{level} close", sv=speed_val: (
                    l20lite_hand.speed.set_speeds([sv] * 10),
                    track(lbl, [28.0, 100.0, 0.0, 0.0, 0.0, 0.0] + [100.0] * 4),
                ),
                expected=(
                    f"Fingers close at {level} speed "
                    f"({'slow' if level == 'LOW' else 'medium' if level == 'MID' else 'fast'})"
                ),
            )

            # Open fingers
            session.step(
                instruction=f"[{level} speed={speed_val}] Opening hand",
                action=lambda lbl=f"{level} open", sv=speed_val: (
                    track(lbl, [100.0] * 10),
                ),
                expected="Fingers fully open",
            )

        session.run()

        _move_and_time(l20lite_hand, [100.0] * 10)

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
