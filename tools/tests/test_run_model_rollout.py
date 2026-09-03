import tempfile
import unittest
from pathlib import Path

from tools.run_model_rollout import Rollout


class ModelRolloutConfigTest(unittest.TestCase):
    def test_relative_paths_are_rooted_at_repository(self):
        path = Rollout.resolve_path("config/runtime/model_deployment.yaml")
        self.assertTrue(path.is_absolute())
        self.assertTrue(path.name == "model_deployment.yaml")

    def test_require_enabled_rejects_disabled_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "disabled.yaml"
            path.write_text("enabled: false\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                Rollout.require_enabled(path, "model")

    def test_configured_topics_are_deduplicated_for_recording(self):
        topics = ["/a", "/a", "/b"]
        self.assertEqual(list(dict.fromkeys(topics)), ["/a", "/b"])


if __name__ == "__main__":
    unittest.main()
