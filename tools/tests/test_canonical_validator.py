#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from validate_canonical_episode import validate_manifest, validate_rows  # noqa: E402


class CanonicalValidatorTest(unittest.TestCase):
    def manifest(self, buffer="A_action"):
        return {
            "schema_version": "teleop_episode/v0.1", "episode_id": "e1", "source": "simulation",
            "collection_mode": "teleop_rule", "intended_uses": ["filter_training"],
            "task": {}, "configuration": {}, "clock": {}, "frames": {}, "calibration": {},
            "action_spec": {"representation": "joint_position", "frame": "B", "dimension": 1, "units": ["rad"], "controller_interface": "sim"},
            "streams": {"control": {}, "task_context": {}, "events": {}, "commands": {}},
            "terminal_audit": {"buffer": buffer, "success": True, "safety_violation": False, "unlogged_external_override": False},
            "data_integrity": {"complete_causal_record": True, "synchronization_valid": True}, "provenance": {}
        }

    def test_filter_gate_and_observed_action(self):
        self.assertEqual(validate_manifest(self.manifest()), [])
        rows = [{"header_stamp_ns": 1, "master_joint_raw": [0.0], "filter_output_action": [0.0], "mapped_joint_command_rad": [0.0], "robot_joint_state_rad": [0.0]}]
        self.assertEqual(validate_rows(rows, require_executed=True), ["row[0].executed_joint_command_rad_missing"])
        rows[0]["executed_joint_command_rad"] = [0.0]
        self.assertEqual(validate_rows(rows, require_executed=True), [])


if __name__ == "__main__":
    unittest.main()
