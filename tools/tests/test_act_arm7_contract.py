import types
import unittest

import numpy as np

from tools.act_arm7_contract import (
    CAMERA_KEYS,
    IMAGE_CHW,
    normalize_action_units,
    ros_joint_positions,
    should_reset_action_chunk,
    validate_action,
    validate_image_chw,
    validate_policy_config,
    validate_runtime_config,
    validate_state,
)


class ActArm7ContractTest(unittest.TestCase):
    def runtime_config(self):
        return {
            "action_contract": "arm7",
            "state_dim": 7,
            "action_dim": 7,
            "image_shape": [480, 640],
            "camera_keys": {CAMERA_KEYS[0]: "/main", CAMERA_KEYS[1]: "/aux"},
        }

    def test_runtime_contract_is_strict(self):
        validate_runtime_config(self.runtime_config())
        invalid = self.runtime_config()
        invalid["action_dim"] = 13
        with self.assertRaises(ValueError):
            validate_runtime_config(invalid)

    def test_policy_contract_matches_trained_features(self):
        policy_config = types.SimpleNamespace(
            input_features={
                "observation.state": types.SimpleNamespace(shape=(7,)),
                CAMERA_KEYS[0]: types.SimpleNamespace(shape=IMAGE_CHW),
                CAMERA_KEYS[1]: types.SimpleNamespace(shape=IMAGE_CHW),
            },
            output_features={"action": types.SimpleNamespace(shape=(7,))},
        )
        validate_policy_config(policy_config)
        policy_config.output_features["action"].shape = (13,)
        with self.assertRaises(ValueError):
            validate_policy_config(policy_config)

    def test_vectors_and_image_are_dimension_checked(self):
        self.assertEqual(validate_state(np.zeros(7, dtype=np.float32)).shape, (7,))
        self.assertEqual(validate_action(np.zeros(7, dtype=np.float32)).shape, (7,))
        self.assertEqual(validate_image_chw(np.zeros(IMAGE_CHW, dtype=np.uint8)).shape, IMAGE_CHW)
        with self.assertRaises(ValueError):
            validate_state(np.zeros(13, dtype=np.float32))
        with self.assertRaises(ValueError):
            validate_image_chw(np.zeros((3, 480, 848), dtype=np.uint8))

    def test_action_units_must_be_radians(self):
        config = self.runtime_config()
        validate_runtime_config(config)
        config["action_units"] = "degrees"
        with self.assertRaises(ValueError):
            validate_runtime_config(config)
        self.assertEqual(normalize_action_units("rad"), "radians")
        converted = ros_joint_positions(np.array([0.0, np.pi], dtype=np.float32), "radians")
        np.testing.assert_allclose(converted, [0.0, 180.0], atol=1e-4)

    def test_late_inference_resets_action_chunk(self):
        self.assertFalse(
            should_reset_action_chunk(
                last_timestamp_ns=0, timestamp_ns=100_000_000, inference_hz=10.0)
        )
        self.assertTrue(
            should_reset_action_chunk(
                last_timestamp_ns=0, timestamp_ns=200_000_000, inference_hz=10.0)
        )
        self.assertTrue(
            should_reset_action_chunk(
                last_timestamp_ns=0, timestamp_ns=50_000_000, inference_hz=10.0, requested=True)
        )


if __name__ == "__main__":
    unittest.main()
