import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_capture_artifacts import validate


class ValidateCaptureArtifactsTest(unittest.TestCase):
    def make_run(self, root: Path) -> None:
        artifacts = root / "artifacts" / "rosbag2"
        artifacts.mkdir(parents=True)
        (artifacts / "metadata.yaml").write_text("rosbag2_bagfile_information: {}\n")
        (artifacts / "bag_0.db3").write_bytes(b"db")
        (root / "artifacts/teleop_capture_manifest.json").write_text(json.dumps({
            "schema": "robot_teleop.teleop-capture/v1", "topics": ["/teleop/events"],
        }))

    def test_accepts_closed_correction_and_terminal_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_run(root)
            (root / "artifacts/audit_events.jsonl").write_text("\n".join([
                json.dumps({"timestamp_ns": 10, "event_type": "correction_start"}),
                json.dumps({"timestamp_ns": 20, "event_type": "correction_end"}),
            ]) + "\n")
            (root / "artifacts/terminal_audit.json").write_text(json.dumps({
                "schema": "robot_teleop.terminal-audit/v0.1", "success": True,
            }))
            self.assertEqual(validate(root, require_terminal_audit=True), [])

    def test_rejects_unclosed_correction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_run(root)
            (root / "artifacts/audit_events.jsonl").write_text(json.dumps({
                "timestamp_ns": 10, "event_type": "correction_start",
            }) + "\n")
            self.assertIn("correction_interval_unclosed", validate(root))


if __name__ == "__main__":
    unittest.main()
