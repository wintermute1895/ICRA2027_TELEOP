#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from train_trajectory_filter import build_windows  # noqa: E402


def row(index: int, *, residual: bool) -> dict:
    value = float(index) / 100.0
    result = {
        "episode_id": "residual-contract", "success": True,
        "master_joint_raw": [value, value],
        "robot_joint_state_rad": [value, value],
        "controller_command_rad": [value, value],
        "action_target_source": "synthetic_smoke_only",
    }
    if residual:
        result["residual_target_rad"] = [0.01, -0.01]
    return result


class ResidualTrainingContractTest(unittest.TestCase):
    def test_controller_command_is_not_accepted_as_residual_supervision(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "episode.jsonl"
            path.write_text("".join(json.dumps(row(i, residual=False)) + "\n" for i in range(8)))
            with self.assertRaisesRegex(ValueError, "expert_action_target_rad"):
                build_windows(path, history_length=3, horizon=1, context_dim=0)

    def test_explicit_residual_target_builds_single_step_windows(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "episode.jsonl"
            path.write_text("".join(json.dumps(row(i, residual=True)) + "\n" for i in range(8)))
            windows = build_windows(path, history_length=3, horizon=1, context_dim=0, allow_synthetic_smoke=True)
            self.assertEqual(windows.targets.shape, (5, 1, 2))
            self.assertEqual(windows.visuals, None)

    def test_expert_action_target_is_preferred_and_correction_is_weighted(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "episode.jsonl"
            rows = []
            for i in range(8):
                item = row(i, residual=False)
                item["expert_action_target_rad"] = [0.2, -0.2]
                item["correction_interval"] = [3, 4]
                rows.append(item)
            path.write_text("".join(json.dumps(item) + "\n" for item in rows))
            windows = build_windows(
                path, history_length=3, horizon=1, context_dim=0, correction_loss_weight=2.0
            )
            self.assertEqual(windows.target_semantics, "recorded_expert_action")
            self.assertEqual(windows.command_semantics, "master_joint_raw")
            self.assertEqual(windows.targets.shape, (5, 1, 2))
            self.assertEqual(windows.correction_weights[:, 0, 0].tolist(), [3.0, 3.0, 1.0, 1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
