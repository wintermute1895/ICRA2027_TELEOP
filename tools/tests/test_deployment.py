import unittest
import numpy as np
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from robot_teleop.deployment import ActionSupervisor, DeploymentLimits, DeploymentMode  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
