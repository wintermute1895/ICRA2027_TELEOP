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
        model = config.model_config(action_dim=7, state_dim=7, command_dim=14)
        self.assertEqual(model.action_dim, 7)
        self.assertEqual(model.horizon, 8)
        self.assertTrue(model.gain_current_command)
        self.assertEqual(model.effective_command_dim, 14)

    def test_cv_residual_action_only_configs_match_except_latent_model(self):
        deterministic = FilterTrainingConfig.from_mapping(yaml.safe_load(
            (ROOT / "config/filters/deterministic_cv_residual_action_only.yaml").read_text()
        ))
        cvae = FilterTrainingConfig.from_mapping(yaml.safe_load(
            (ROOT / "config/filters/cvae_cv_residual_action_only.yaml").read_text()
        ))
        self.assertEqual(deterministic.data.target_representation, "residual_over_constant_velocity")
        self.assertEqual(cvae.data.target_representation, "residual_over_constant_velocity")
        self.assertEqual(deterministic.model["visual_dim"], cvae.model["visual_dim"])
        self.assertEqual(deterministic.model["history_length"], cvae.model["history_length"])
        self.assertEqual(deterministic.model["horizon"], cvae.model["horizon"])
        self.assertFalse(deterministic.model["gain_enabled"])
        self.assertFalse(cvae.model["gain_enabled"])

    def test_rejects_undeclared_target_semantics(self):
        payload = yaml.safe_load((ROOT / "config/filters/trajectory_cvae_transformer_v0_1.yaml").read_text())
        payload["semantics"]["target"] = "ambiguous"
        with self.assertRaisesRegex(ValueError, "expert_action_target_rad"):
            FilterTrainingConfig.from_mapping(payload)


if __name__ == "__main__":
    unittest.main()
