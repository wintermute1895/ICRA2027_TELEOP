#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from teleop_filter import SafetyLimits, SafetyProjector  # noqa: E402


class SafetyProjectorTest(unittest.TestCase):
    def test_applies_magnitude_rate_position_and_velocity_limits(self):
        limits = SafetyLimits(
            np.array([-1.0, -1.0]), np.array([1.0, 1.0]),
            max_residual_rad=0.2, max_residual_rate_rad_s=0.1,
            max_command_velocity_rad_s=0.5, max_model_age_ms=100.0,
        )
        projector = SafetyProjector(limits)
        first = projector.project(
            np.array([0.0, 0.0]), np.array([1.0, -1.0]),
            dt_s=1.0, model_age_ms=1.0,
        )
        self.assertTrue(np.allclose(first.command_rad, [0.1, -0.1]))
        second = projector.project(
            np.array([0.1, -0.1]), np.array([1.0, -1.0]),
            dt_s=0.1, model_age_ms=1.0,
        )
        self.assertTrue(np.all(np.abs(second.applied_residual_rad) <= 0.2))

    def test_timeout_falls_back_to_baseline(self):
        projector = SafetyProjector(SafetyLimits(
            np.array([-1.0]), np.array([1.0]), 0.2, 1.0, 1.0, 10.0,
        ))
        result = projector.project(np.array([0.3]), np.array([0.1]), dt_s=0.1, model_age_ms=11.0)
        self.assertTrue(result.fallback)
        self.assertIn("model_timeout", result.reasons)
        self.assertTrue(np.allclose(result.command_rad, [0.3]))


if __name__ == "__main__":
    unittest.main()
