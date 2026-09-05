import unittest
import numpy as np
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from robot_teleop.deployment import (  # noqa: E402
    ActiveModelGate,
    ActionSupervisor,
    DeploymentLimits,
    DeploymentMode,
)


class DeploymentTest(unittest.TestCase):
    def test_shadow_never_selects_candidate(self):
        supervisor = ActionSupervisor(mode=DeploymentMode.SHADOW)
        result = supervisor.decide([0.0, 0.0], [0.01, 0.01], candidate_time=0.0, now=0.0)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "shadow_mode")

    def test_active_rejects_stale_invalid_and_oversized_candidates(self):
        supervisor = ActionSupervisor(mode=DeploymentMode.ACTIVE, timeout_s=0.3)
        self.assertEqual(supervisor.decide([0.0], [0.1], candidate_time=0.0, now=1.0).reason, "candidate_stale_or_missing")
        self.assertEqual(supervisor.decide([0.0], [float("nan")], candidate_time=0.0, now=0.0).reason, "candidate_invalid")
        self.assertEqual(supervisor.decide([0.0], [0.06], candidate_time=0.0, now=0.0).reason, "candidate_delta_exceeded")

    def test_active_accepts_bounded_candidate_and_checks_step(self):
        supervisor = ActionSupervisor(mode=DeploymentMode.ACTIVE, limits=DeploymentLimits(max_delta_rad=0.1, max_step_rad=0.05))
        result = supervisor.decide(np.zeros(2), [0.01, -0.01], candidate_time=0.0, now=0.1, previous_rad=[0.0, 0.0])
        self.assertTrue(result.accepted)
        self.assertEqual(result.source, "candidate")
        result = supervisor.decide(np.zeros(1), [0.06], candidate_time=0.0, now=0.1, previous_rad=[0.0])
        self.assertEqual(result.reason, "candidate_step_exceeded")

    def test_invalid_fallback_is_rejected_without_selecting_candidate(self):
        supervisor = ActionSupervisor(mode=DeploymentMode.ACTIVE)
        with self.assertRaises(ValueError):
            supervisor.decide([float("nan")], [0.0], candidate_time=0.0, now=0.0)


class ActiveModelGateTest(unittest.TestCase):
    def _gate(self):
        return ActiveModelGate(
            timeout_s=0.3,
            limits=DeploymentLimits(max_delta_rad=0.1, max_step_rad=0.05),
            max_step_rate_rad_s=0.2,
        )

    def test_no_measured_state_never_publishes(self):
        gate = self._gate()
        outcome = gate.consider(
            base_rad=None,
            candidate_rad=np.zeros(7),
            candidate_time_s=0.0,
            now_s=0.0,
        )
        self.assertEqual(outcome.state, "WAITING_FOR_MODEL")
        self.assertFalse(outcome.publish)
        self.assertEqual(outcome.reason, "measured_state_unavailable")

    def test_no_candidate_or_stale_candidate_keeps_waiting(self):
        base = np.zeros(7, dtype=np.float32)
        gate = self._gate()
        missing = gate.consider(
            base_rad=base, candidate_rad=None,
            candidate_time_s=None, now_s=0.0)
        self.assertFalse(missing.publish)
        self.assertEqual(missing.reason, "model_candidate_missing")
        stale = gate.consider(
            base_rad=base, candidate_rad=np.zeros(7),
            candidate_time_s=0.0, now_s=10.0)
        self.assertFalse(stale.publish)
        self.assertEqual(stale.reason, "model_candidate_stale")

    def test_first_accepted_command_transitions_to_active_control(self):
        gate = self._gate()
        base = np.zeros(7, dtype=np.float32)
        candidate = np.full(7, 0.02, dtype=np.float32)
        first = gate.consider(
            base_rad=base,
            candidate_rad=candidate,
            candidate_time_s=0.0,
            now_s=0.0,
        )
        self.assertTrue(first.publish)
        self.assertTrue(first.first_command)
        self.assertEqual(first.state, "ACTIVE_CONTROL")
        np.testing.assert_allclose(first.command_rad, candidate)
        second = gate.consider(
            base_rad=base,
            candidate_rad=np.zeros(7),
            candidate_time_s=0.0,
            now_s=1.0,
        )
        self.assertFalse(second.first_command)

    def test_rejected_delta_is_not_published(self):
        gate = self._gate()
        base = np.zeros(7, dtype=np.float32)
        outcome = gate.consider(
            base_rad=base,
            candidate_rad=np.full(7, 0.5, dtype=np.float32),
            candidate_time_s=0.0,
            now_s=0.0,
        )
        self.assertFalse(outcome.publish)
        self.assertEqual(outcome.state, "WAITING_FOR_MODEL")
        self.assertEqual(outcome.reason, "candidate_delta_exceeded")

    def test_ramp_bounds_first_output_after_reference(self):
        gate = ActiveModelGate(
            timeout_s=0.3,
            limits=DeploymentLimits(max_delta_rad=0.1, max_step_rad=0.05),
            max_step_rate_rad_s=1.0,
        )
        base = np.zeros(7, dtype=np.float32)
        previous = np.full(7, 0.0, dtype=np.float32)
        outcome = gate.consider(
            base_rad=base,
            candidate_rad=np.full(7, 0.05, dtype=np.float32),
            candidate_time_s=0.0,
            now_s=0.01,
            previous_rad=previous,
            last_output_time_s=0.0,
        )
        self.assertTrue(outcome.publish)
        self.assertEqual(outcome.reason, "accepted_ramped")
        np.testing.assert_allclose(outcome.command_rad, np.full(7, 0.01))


if __name__ == "__main__":
    unittest.main()
