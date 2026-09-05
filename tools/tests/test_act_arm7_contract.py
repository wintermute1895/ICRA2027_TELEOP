import types
import unittest

import numpy as np

from tools.act_arm7_contract import (
    CAMERA_KEYS,
    IMAGE_CHW,
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


if __name__ == "__main__":
    unittest.main()
