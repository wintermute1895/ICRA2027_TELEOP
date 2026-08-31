#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ExportedJsonlCanonicalTest(unittest.TestCase):
    def test_missing_tcp_and_context_can_be_a_action_and_preserves_tactile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            exported = root / "episode.jsonl"
            exported.write_text(json.dumps({
                "episode_id": "e1", "arm": "right", "header_stamp_ns": 10,
                "joint_names": ["j1"], "robot_joint_state_rad": [0.1],
                "master_joint_raw": [0.2], "master_joint_filtered_rad": [0.2],
                "mapped_joint_command_rad": [0.2], "controller_command_rad": [0.2],
                "tactile_force": {"value": [1.0]},
            }) + "\n", encoding="utf-8")
            events = root / "episode.jsonl.events.jsonl"
            events.write_text(json.dumps({
                "timestamp_ns": 10, "severity": "info", "source": "human_auditor_keyboard",
                "event_type": "align", "payload": {"key": "2"},
            }) + "\n", encoding="utf-8")
            (root / "episode.jsonl.manifest.json").write_text(json.dumps({
                "audit_events_sidecar": str(events),
            }), encoding="utf-8")
            audit = root / "audit.json"
            audit.write_text(json.dumps({"success": True, "termination_reason": "operator_verified", "safety_violation": False, "unlogged_external_override": False}), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(ROOT / "tools/exported_jsonl_to_canonical_episode.py"),
                "--export-jsonl", str(exported), "--output-dir", str(root / "canonical"),
                "--source", "real", "--task-id", "usb_c_insertion", "--terminal-audit", str(audit),
            ], text=True, capture_output=True, check=True)
            manifest = json.loads((root / "canonical/episode.manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["terminal_audit"]["buffer"], "A_action")
            self.assertIn("filter_training", manifest["intended_uses"])
            self.assertEqual(manifest["terminal_audit"]["failed_gates"], [])
            self.assertEqual(manifest["streams"]["tactile"]["availability"], "available")
            self.assertEqual(manifest["frames"], {})
            self.assertEqual(manifest["calibration"], {})
            self.assertEqual(manifest["streams"]["control"]["storage_ref"], "streams/control.jsonl")
            event_rows = [json.loads(line) for line in (root / "canonical/streams/events.jsonl").read_text().splitlines()]
            self.assertEqual(event_rows[0]["event_type"], "align")
            self.assertEqual(json.loads((root / "canonical/validator_report.json").read_text())["passed"], True)
            self.assertIn("A_action", result.stdout)
            filter_output = root / "filter/filter_training.jsonl"
            subprocess.run([
                sys.executable, str(ROOT / "tools/canonical_episode_to_filter_jsonl.py"),
                "--manifest", str(root / "canonical/episode.manifest.json"),
                "--output", str(filter_output),
            ], text=True, capture_output=True, check=True)
            projected = [json.loads(line) for line in filter_output.read_text().splitlines()]
            self.assertEqual(len(projected), 1)
            self.assertEqual(projected[0]["master_joint_raw"], [0.2])
            self.assertEqual(projected[0]["arm"], "right")

    def test_policy_training_is_independent_from_filter_causal_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            exported = root / "episode.jsonl"
            rows = []
            for index in range(20):
                rows.append({
                    "episode_id": "policy-only", "arm": "right", "header_stamp_ns": index + 1,
                    "joint_names": ["j1"], "robot_joint_state_rad": [0.1],
                    "master_joint_raw": None if index == 0 else [0.2],
                    "master_joint_filtered_rad": None if index == 0 else [0.2],
                    "mapped_joint_command_rad": None if index == 0 else [0.2],
                    "controller_command_rad": [0.2],
                    "rgb": {"topic": "/camera/color/image_raw", "header_stamp_ns": index + 1},
                })
            exported.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            audit = root / "audit.json"
            audit.write_text(json.dumps({"success": True, "termination_reason": "operator_verified", "safety_violation": False, "unlogged_external_override": False}), encoding="utf-8")
            subprocess.run([
                sys.executable, str(ROOT / "tools/exported_jsonl_to_canonical_episode.py"),
                "--export-jsonl", str(exported), "--output-dir", str(root / "canonical"),
                "--source", "real", "--task-id", "precision_alignment", "--terminal-audit", str(audit),
            ], text=True, capture_output=True, check=True)
            manifest = json.loads((root / "canonical/episode.manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["intended_uses"], ["policy_training"])
            self.assertEqual(manifest["terminal_audit"]["buffer"], "A_audit")
            self.assertFalse(manifest["data_integrity"]["complete_causal_record"])
            self.assertTrue(manifest["data_integrity"]["policy_training_admitted"])


if __name__ == "__main__":
    unittest.main()
