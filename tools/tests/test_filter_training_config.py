import unittest

from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from teleop_filter import FilterTrainingConfig  # noqa: E402


class FilterTrainingConfigTest(unittest.TestCase):
    def test_repository_visual_config_is_valid(self):
        payload = yaml.safe_load((ROOT / "config/filters/trajectory_cvae_transformer_v0_2_vlm.yaml").read_text())
        config = FilterTrainingConfig.from_mapping(payload)
        self.assertEqual(config.visual_dim, 1536)
        self.assertEqual(config.loss.correction_weight, 2.0)
        self.assertFalse(config.data.allow_synthetic_smoke)
        self.assertEqual(config.model_config(action_dim=7, state_dim=7).action_dim, 7)

    def test_rejects_undeclared_target_semantics(self):
        payload = yaml.safe_load((ROOT / "config/filters/trajectory_cvae_transformer_v0_1.yaml").read_text())
        payload["semantics"]["target"] = "ambiguous"
        with self.assertRaisesRegex(ValueError, "expert_action_target_rad"):
            FilterTrainingConfig.from_mapping(payload)


if __name__ == "__main__":
    unittest.main()
