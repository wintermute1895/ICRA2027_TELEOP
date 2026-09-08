import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CorrectionSegmentViewTest(unittest.TestCase):
    def test_events_create_mask_and_recorded_action_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "episode.jsonl"
            episode.write_text("".join(json.dumps({
                "timestamp_ns": stamp,
                "master_joint_raw": [0.0, 0.0],
                "controller_command_rad": [0.1, -0.1],
                "success": True,
            }) + "\n" for stamp in (100, 200, 300)))
            events = root / "events.jsonl"
            events.write_text("".join(json.dumps({"timestamp_ns": stamp, "event_type": kind}) + "\n" for stamp, kind in ((150, "correction_start"), (250, "correction_end"))))
            output = root / "view.jsonl"
            subprocess.run([
                sys.executable, str(ROOT / "tools/build_correction_segment_view.py"),
                "--episode", str(episode), "--events", str(events),
                "--expert-action-field", "controller_command_rad", "--output", str(output),
            ], check=True, text=True, capture_output=True)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual([row["correction_mask"] for row in rows], [0, 1, 0])
            self.assertEqual(rows[1]["expert_action_target_rad"], [0.1, -0.1])
            self.assertEqual(rows[1]["action_target_source"], "selected:controller_command_rad")

    def test_preserves_assisted_executed_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "episode.jsonl"
            episode.write_text(json.dumps({
                "timestamp_ns": 100, "master_joint_raw": [0.0],
                "executed_joint_command_rad": [0.2], "expert_action_target_rad": [0.2],
                "action_target_source": "executed_assisted_action", "success": True,
            }) + "\n")
            output = root / "view.jsonl"
            subprocess.run([
                sys.executable, str(ROOT / "tools/build_correction_segment_view.py"),
                "--episode", str(episode), "--expert-action-field", "master_joint_raw",
                "--output", str(output),
            ], check=True, text=True, capture_output=True)
            row = json.loads(output.read_text())
            self.assertEqual(row["expert_action_target_rad"], [0.2])
            self.assertEqual(row["action_target_source"], "executed_assisted_action")

    def test_rejects_unmatched_correction_end(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "episode.jsonl"
            episode.write_text(json.dumps({
                "timestamp_ns": 100, "controller_command_rad": [0.1], "success": True,
            }) + "\n")
            events = root / "events.jsonl"
            events.write_text(json.dumps({"timestamp_ns": 100, "event_type": "correction_end"}) + "\n")
            output = root / "view.jsonl"
            result = subprocess.run([
                sys.executable, str(ROOT / "tools/build_correction_segment_view.py"),
                "--episode", str(episode), "--events", str(events),
                "--expert-action-field", "controller_command_rad", "--output", str(output),
            ], text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("correction_end has no matching", result.stderr)


if __name__ == "__main__":
    unittest.main()
