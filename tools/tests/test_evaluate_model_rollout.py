import tempfile
import unittest
from pathlib import Path

from tools.evaluate_model_rollout import bag_path, camera_args


class EvaluateModelRolloutTest(unittest.TestCase):
    def test_accepts_rollout_directory_or_bag_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bag = root / "artifacts" / "rosbag2"
            bag.mkdir(parents=True)
            (bag / "metadata.yaml").write_text("rosbag2_bagfile_information: {}\n", encoding="utf-8")
            self.assertEqual(bag_path(root), bag)
            self.assertEqual(bag_path(bag), bag)

    def test_camera_mapping_comes_from_rollout_config(self):
        config = {"cameras": [{"id": "main_rgb", "namespace": "/camera/camera"}]}
        self.assertEqual(camera_args(config, []), [
            "--camera-namespace", "/camera/camera", "--camera-id", "main_rgb",
        ])

    def test_explicit_camera_mapping_replaces_defaults(self):
        config = {"cameras": [{"id": "old", "namespace": "/old"}]}
        self.assertEqual(camera_args(config, ["main=/new"]), [
            "--camera-namespace", "/new", "--camera-id", "main",
        ])


if __name__ == "__main__":
    unittest.main()
