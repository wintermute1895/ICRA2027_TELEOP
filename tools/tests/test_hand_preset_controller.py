import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.hand_preset_controller import cached_o6_angles, load_config, next_preset, validate_config


class HandPresetControllerTest(unittest.TestCase):
    def test_supplied_config_has_binary_cycle(self):
        root = Path(__file__).resolve().parents[2]
        config = validate_config(load_config(root / "config/hand_presets.json"), "right")
        self.assertEqual(config["cycle"], ["gesture_0_open", "gesture_1_grasp", "gesture_2_grasp", "gesture_3_grasp"])
        self.assertEqual([config["presets"][name]["gripper_state"] for name in config["cycle"]], [0, 1, 1, 1])
        expected = {
            "gesture_0_open": [100.0, 100.0, 99.6078431372549, 99.2156862745098, 99.2156862745098, 99.2156862745098],
            "gesture_1_grasp": [100.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "gesture_2_grasp": [46.0, 30.0, 46.0, 100.0, 100.0, 100.0],
            "gesture_3_grasp": [60.0, 24.0, 12.0, 7.0, 0.0, 0.0],
        }
        for name, values in expected.items():
            self.assertEqual(config["presets"][name]["source_positions"], values)

    def test_cycle_wraps(self):
        self.assertEqual(next_preset(["grasp", "open", "release"], -1), (0, "grasp"))
        self.assertEqual(next_preset(["grasp", "open", "release"], 2), (0, "grasp"))

    def test_invalid_binary_state_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps({"hands": {"right": {"cycle": ["x"], "presets": {"x": {"positions": [1], "gripper_state": 2}}}}}))
            with self.assertRaises(SystemExit):
                validate_config(load_config(path), "right")

    def test_cached_o6_angles_is_nonblocking_and_validated(self):
        angles = SimpleNamespace(to_list=lambda: [10, 20, 30, 40, 50, 60])
        hand = SimpleNamespace(get_snapshot=lambda: SimpleNamespace(angle=SimpleNamespace(angles=angles)))
        self.assertEqual(cached_o6_angles(hand), [10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
        missing = SimpleNamespace(get_snapshot=lambda: SimpleNamespace(angle=None))
        self.assertIsNone(cached_o6_angles(missing))

    def test_controller_path_execution_bootstraps_repository_imports(self):
        root = Path(__file__).resolve().parents[2]
        controller = root / "tools" / "hand_preset_controller.py"
        code = (
            f"import runpy; runpy.run_path({str(controller)!r}, run_name='path_test'); "
            "from src.hand import O6Hand; from src.hand.o6 import O6_JOINT_NAMES; "
            "assert len(O6_JOINT_NAMES) == 6"
        )
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        result = subprocess.run(
            ["/usr/bin/python3", "-c", code], cwd="/tmp", env=environment,
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_vendored_o6_import_does_not_require_arm_scipy(self):
        root = Path(__file__).resolve().parents[2]
        code = (
            "from pathlib import Path; import sys; "
            f"sys.path.insert(0, {str(root / 'third_party/linkerbot-python-sdk-main/src')!r}); "
            "from linkerbot.hand.o6 import O6; assert O6 is not None"
        )
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        result = subprocess.run(
            ["/usr/bin/python3", "-c", code], cwd="/tmp", env=environment,
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
