import types
import unittest

import numpy as np

from tools.imle_arm7_contract import (
    CAMERA_KEYS,
    IMAGE_CHW,
    executed_chunk,
    normalize_action_units,
    ros_joint_positions,
    select_candidate_index,
    should_reset_action_chunk,
    validate_action,
    validate_image_chw,
    validate_payload_config,
    validate_runtime_config,
    validate_state,
)


class ImleArm7ContractTest(unittest.TestCase):
    def runtime_config(self):
        return {
            "schema": "robot_teleop.imle-runtime/v1",
            "action_contract": "arm7",
            "action_units": "degrees",
            "state_dim": 7,
            "action_dim": 7,
            "obs_horizon": 2,
            "pred_horizon": 16,
            "action_horizon": 8,
            "candidate_count": 20,
            "image_shape": [480, 640],
            "camera_keys": {CAMERA_KEYS[0]: "/main", CAMERA_KEYS[1]: "/aux"},
        }

    def test_runtime_contract_is_strict(self):
        validate_runtime_config(self.runtime_config())
        invalid = self.runtime_config()
        invalid["action_dim"] = 13
        with self.assertRaises(ValueError):
            validate_runtime_config(invalid)

    def test_action_units_must_be_degrees(self):
        config = self.runtime_config()
        validate_runtime_config(config)
        config["action_units"] = "radians"
        with self.assertRaises(ValueError):
            validate_runtime_config(config)
        self.assertEqual(normalize_action_units("deg"), "degrees")
        converted = ros_joint_positions(np.array([0.0, 90.0], dtype=np.float32), "degrees")
        np.testing.assert_allclose(converted, [0.0, 90.0], atol=1e-4)

    def test_vectors_and_image_are_dimension_checked(self):
        self.assertEqual(validate_state(np.zeros(7, dtype=np.float32)).shape, (7,))
        self.assertEqual(validate_action(np.zeros(7, dtype=np.float32)).shape, (7,))
        self.assertEqual(validate_image_chw(np.zeros(IMAGE_CHW, dtype=np.uint8)).shape, IMAGE_CHW)
        with self.assertRaises(ValueError):
            validate_state(np.zeros(13, dtype=np.float32))
        with self.assertRaises(ValueError):
            validate_image_chw(np.zeros((3, 480, 848), dtype=np.uint8))

    def test_payload_horizon_is_checked(self):
        runtime = types.SimpleNamespace(
            obs_horizon=2, pred_horizon=16, action_horizon=8, candidate_count=20, image_size=(480, 640)
        )
        validate_payload_config(runtime)
        runtime.pred_horizon = 8
        with self.assertRaises(ValueError):
            validate_payload_config(runtime)

    def test_late_inference_resets_action_chunk(self):
        self.assertFalse(
            should_reset_action_chunk(
                last_timestamp_ns=0, timestamp_ns=20_000_000, inference_hz=50.0)
        )
        self.assertTrue(
            should_reset_action_chunk(
                last_timestamp_ns=0, timestamp_ns=40_000_000, inference_hz=50.0)
        )
        self.assertTrue(
            should_reset_action_chunk(
                last_timestamp_ns=0, timestamp_ns=1, inference_hz=50.0, requested=True)
        )

    def test_first_plan_is_random_later_plans_use_overlap(self):
        rng = np.random.default_rng(0)
        candidates = np.zeros((20, 16, 7), dtype=np.float32)
        candidates[3, :, :] = 1.0
        first = select_candidate_index(candidates, None, rng=rng)
        self.assertGreaterEqual(first, 0)
        self.assertLess(first, 20)
        previous = np.zeros((16, 7), dtype=np.float32)
        previous[8:16] = 1.0
        self.assertEqual(select_candidate_index(candidates, previous), 3)

    def test_executed_chunk_is_the_first_eight_steps(self):
        trajectory = np.arange(16 * 7, dtype=np.float32).reshape(16, 7)
        chunk = executed_chunk(trajectory)
        self.assertEqual(chunk.shape, (8, 7))
        np.testing.assert_array_equal(chunk, trajectory[:8])


if __name__ == "__main__":
    unittest.main()
