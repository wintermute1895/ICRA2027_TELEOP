#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ExportedJsonlCanonicalTest(unittest.TestCase):
    def test_missing_context_is_audit_only_and_preserves_tactile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            exported = root / "episode.jsonl"
            exported.write_text(json.dumps({
                "episode_id": "e1", "arm": "right", "header_stamp_ns": 10,
                "joint_names": ["j1"], "robot_joint_state_rad": [0.1],
                "master_joint_raw": [0.2], "master_joint_filtered_rad": [0.2],
                "mapped_joint_command_rad": [0.2], "controller_command_rad": [0.2],
                "tcp_pose_base": [0, 0, 0, 0, 0, 0, 1],
                "tactile_force": {"value": [1.0]},
            }) + "\n", encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(ROOT / "tools/exported_jsonl_to_canonical_episode.py"),
                "--export-jsonl", str(exported), "--output-dir", str(root / "canonical"),
                "--source", "real", "--task-id", "usb_c_insertion",
            ], text=True, capture_output=True, check=True)
            manifest = json.loads((root / "canonical/episode.manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["terminal_audit"]["buffer"], "A_audit")
            self.assertEqual(manifest["intended_uses"], ["audit_only"])
            self.assertIn("incomplete_causal_record", manifest["terminal_audit"]["failed_gates"])
            self.assertEqual(manifest["streams"]["tactile"]["availability"], "available")
            self.assertEqual(json.loads((root / "canonical/validator_report.json").read_text())["passed"], True)
            self.assertIn("A_audit", result.stdout)


if __name__ == "__main__":
    unittest.main()
