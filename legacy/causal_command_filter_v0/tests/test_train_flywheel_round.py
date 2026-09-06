#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "legacy/causal_command_filter_v0"))

from train_flywheel_round import train_round  # noqa: E402


class FlywheelRoundTest(unittest.TestCase):
    def write_episode(self, root: Path, episode_id: str) -> dict:
        manifest = {
            "schema_version": "teleop_episode/v0.1", "episode_id": episode_id,
            "source": "simulation", "collection_mode": "teleop_rule", "intended_uses": ["filter_training"],
            "task": {"task_id": "fixture", "task_family": "fixture", "success_spec_version": "v1"},
            "configuration": {"configuration_id": episode_id, "parameters": {}, "split": "train"},
            "clock": {"clock_domain": "fixture", "control_hz": 10, "timestamp_unit": "ns", "alignment_tolerance_ns": 10},
            "frames": {"base_frame": "B", "end_effector_frame": "E"}, "calibration": {"calibration_version": "sim"},
            "action_spec": {"representation": "joint_position", "frame": "B", "dimension": 1, "units": ["rad"], "controller_interface": "fixture", "joint_names": ["j1"]},
            "streams": {"control": {}, "commands": {}, "task_context": {}, "events": {}},
            "terminal_audit": {"buffer": "A_action", "success": True, "safety_violation": False, "unlogged_external_override": False},
            "data_integrity": {"complete_causal_record": True, "synchronization_valid": True}, "provenance": {"code_revision": "fixture"},
        }
        controls, commands = [], []
        for index in range(5):
            stamp, value = index * 10, float(index)
            controls.append({"timestamp_ns": stamp, "robot": {"q_rad": [value]}, "execution": {"controller_command": [value * 0.5]}})
            commands.append({"timestamp_ns": stamp, "raw_teleop": {"value": [value]}, "filter_output": {"value": [value]}, "safety_projected": {"value": [value]}, "controller_command": [value * 0.5]})
        paths = {"manifest": root / f"{episode_id}.manifest.json", "control_jsonl": root / f"{episode_id}.control.jsonl", "commands_jsonl": root / f"{episode_id}.commands.jsonl"}
        paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
        for key, rows in (("control_jsonl", controls), ("commands_jsonl", commands)):
            paths[key].write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return {key: str(value) for key, value in paths.items()}

    def test_train_round_projects_and_reports_episode_splits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = {"schema": "robot_teleop.filter-flywheel-round/v1", "round_id": "fixture", "condition_id": "F_static", "model": {"history_length": 2, "context_size": 0, "ridge": 1e-6}, "episodes": [{"split": "train", **self.write_episode(root, "train")}, {"split": "validation", **self.write_episode(root, "validation")}]}
            config_path, output = root / "round.json", root / "output"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            report = train_round(config_path, output)
            self.assertEqual(report["episodes"], {"train": ["train"], "validation": ["validation"]})
            self.assertGreater(report["metrics"]["train"]["samples"], 0)
            self.assertGreater(report["metrics"]["validation"]["samples"], 0)
            self.assertTrue((output / "causal_filter_model.json").is_file())
            self.assertTrue((output / "round_report.json").is_file())


if __name__ == "__main__":
    unittest.main()
