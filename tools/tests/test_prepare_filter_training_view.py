import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


class PrepareFilterTrainingViewTest(unittest.TestCase):
    def test_script_help_declares_explicit_expert_action_field(self):
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/prepare_filter_training_view.sh"), "--help"],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--expert-action-field", result.stderr)

    def test_script_does_not_reference_third_party_sdk(self):
        source = (ROOT / "scripts/prepare_filter_training_view.sh").read_text(encoding="utf-8")
        self.assertNotIn("third_party", source)

    def test_script_exposes_config_entrypoint(self):
        source = (ROOT / "scripts/prepare_filter_training_view.sh").read_text(encoding="utf-8")
        self.assertIn("--config=", source)
        self.assertIn("tools/prepare_filter_training_view.py", source)

    def test_config_pipeline_builds_correction_view_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode = root / "episode.jsonl"
            events = root / "events.jsonl"
            episode.write_text("".join(json.dumps({
                "timestamp_ns": stamp,
                "controller_command_rad": [0.1, 0.2],
            }) + "\n" for stamp in (100, 150, 200)), encoding="utf-8")
            events.write_text("".join(json.dumps({
                "timestamp_ns": stamp, "event_type": kind,
            }) + "\n" for stamp, kind in ((100, "correction_start"), (200, "correction_end"))), encoding="utf-8")
            config = root / "pipeline.yaml"
            config.write_text(yaml.safe_dump({
                "schema": "robot_teleop.filter-training-pipeline/v0.1",
                "source": {"episode": "episode.jsonl", "events": "events.jsonl", "expert_action_field": "controller_command_rad"},
                "output": {"directory": "output"},
                "vlm": {"enabled": False},
            }), encoding="utf-8")
            command = [sys.executable, str(ROOT / "tools/prepare_filter_training_view.py"), "--config", str(config)]
            first = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            rows = [json.loads(line) for line in (root / "output/correction_view.jsonl").read_text().splitlines()]
            self.assertEqual([row["correction_mask"] for row in rows], [1, 1, 0])
            self.assertTrue((root / "output/pipeline_manifest.json").is_file())
            second = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("refusing to overwrite", second.stderr)

    def test_config_supports_separate_path_form(self):
        source = (ROOT / "scripts/prepare_filter_training_view.sh").read_text(encoding="utf-8")
        self.assertIn('[[ "$arg" == --config=* || "$arg" == --config ]]', source)


if __name__ == "__main__":
    unittest.main()
