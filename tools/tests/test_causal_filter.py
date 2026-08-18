#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ros2_ws/src/sim_robot_driver"))

from sim_robot_driver.causal_filter import blend_command, build_feature, predict, train_ridge


class CausalFilterTest(unittest.TestCase):
    def test_ridge_recovers_causal_action_mapping(self):
        features, targets = [], []
        for value in np.linspace(-0.5, 0.5, 32):
            history = [[value, -value], [value + 0.1, -value + 0.1]]
            state = [0.2, -0.1]
            features.append(build_feature(history, state, 2, 2))
            targets.append([0.5 * history[-1][0] + state[0], 0.5 * history[-1][1] + state[1]])
        model = train_ridge(features, targets, joint_count=2, history_length=2, ridge=1e-8)
        predicted, ood = predict(model, [[0.2, -0.2], [0.3, -0.1]], [0.2, -0.1])
        self.assertLess(ood, 3.0)
        self.assertTrue(np.allclose(predicted, [0.35, -0.15], atol=1e-4))

    def test_ood_falls_back_to_baseline(self):
        feature = build_feature([[0.0], [0.0]], [0.0], 1, 2)
        model = train_ridge([feature, feature + 1e-4], [[0.0], [0.0]], joint_count=1, history_length=2)
        output, diagnostics = blend_command(model, [[100.0], [100.0]], [100.0], blend=1.0, max_correction_rad=0.1, max_ood_z=3.0)
        self.assertEqual(output, [100.0])
        self.assertTrue(diagnostics["fallback"])


    def test_context_is_required_by_context_model(self):
        features, targets = [], []
        for value in np.linspace(-0.2, 0.2, 16):
            features.append(build_feature([[value], [value + 0.01]], [0.0], 1, 2, [value], 1))
            targets.append([2.0 * value])
        model = train_ridge(features, targets, joint_count=1, history_length=2, context_size=1)
        prediction, _ = predict(model, [[0.1], [0.11]], [0.0], [0.1])
        self.assertAlmostEqual(float(prediction[0]), 0.2, places=3)
        with self.assertRaises(ValueError):
            blend_command(model, [[0.1], [0.11]], [0.0], blend=0.5, max_correction_rad=0.1, max_ood_z=3.0)

if __name__ == "__main__":
    unittest.main()
