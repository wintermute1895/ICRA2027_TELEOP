import json
import tempfile
import unittest
from pathlib import Path

from tools.hand_preset_controller import load_config, next_preset, validate_config


class HandPresetControllerTest(unittest.TestCase):
    def test_supplied_config_has_binary_cycle(self):
        root = Path(__file__).resolve().parents[2]
        config = validate_config(load_config(root / "config/hand_presets.json"), "right")
        self.assertEqual(config["cycle"], ["power_grasp", "open"])
        self.assertEqual([config["presets"][name]["gripper_state"] for name in config["cycle"]], [1, 0])

    def test_cycle_wraps(self):
        self.assertEqual(next_preset(["grasp", "open", "release"], -1), (0, "grasp"))
        self.assertEqual(next_preset(["grasp", "open", "release"], 2), (0, "grasp"))

    def test_invalid_binary_state_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps({"hands": {"right": {"cycle": ["x"], "presets": {"x": {"positions": [1], "gripper_state": 2}}}}}))
            with self.assertRaises(SystemExit):
                validate_config(load_config(path), "right")


if __name__ == "__main__":
    unittest.main()
