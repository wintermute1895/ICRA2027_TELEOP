import tempfile
import unittest
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from teleop_filter.pipeline_config import load_pipeline_config  # noqa: E402


class PipelineConfigTest(unittest.TestCase):
    def _write(self, payload):
        root = Path(tempfile.mkdtemp())
        path = root / "pipeline.yaml"
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")
        return path

    def _payload(self):
        return {
            "schema": "robot_teleop.filter-training-pipeline/v0.1",
            "source": {"episode": "episode.jsonl", "expert_action_field": "controller_command_rad"},
            "output": {"directory": "out"},
            "vlm": {"enabled": True, "model_id": "model", "revision": "rev", "cameras": [
                {"id": "main", "index": "main.jsonl"},
            ]},
        }

    def test_resolves_relative_paths_and_defaults(self):
        path = self._write(self._payload())
        config = load_pipeline_config(path)
        self.assertEqual(config.episode, path.parent / "episode.jsonl")
        self.assertEqual(config.cameras[0].camera_id, "main")
        self.assertEqual(config.batch_size, 32)

    def test_rejects_duplicate_camera_ids(self):
        payload = self._payload()
        payload["vlm"]["cameras"].append({"id": "main", "index": "other.jsonl"})
        with self.assertRaisesRegex(ValueError, "duplicate VLM camera id"):
            load_pipeline_config(self._write(payload))

    def test_rejects_enabled_vlm_without_cameras(self):
        payload = self._payload()
        payload["vlm"]["cameras"] = []
        with self.assertRaisesRegex(ValueError, "at least one camera"):
            load_pipeline_config(self._write(payload))

    def test_rejects_string_boolean(self):
        payload = self._payload()
        payload["vlm"]["enabled"] = "false"
        with self.assertRaisesRegex(ValueError, "must be true or false"):
            load_pipeline_config(self._write(payload))

    def test_rejects_unknown_field(self):
        payload = self._payload()
        payload["vlm"]["devcie"] = "cpu"
        with self.assertRaisesRegex(ValueError, "unknown vlm fields: devcie"):
            load_pipeline_config(self._write(payload))


if __name__ == "__main__":
    unittest.main()
