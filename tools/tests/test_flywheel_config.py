import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "src"))

from robot_teleop.flywheel import load_flywheel_config  # noqa: E402


class FlywheelConfigTest(unittest.TestCase):
    def _write(self, enabled: bool):
        root = Path(tempfile.mkdtemp())
        model = root / "model.yaml"
        model.write_text(yaml.safe_dump({
            "model": {"visual_dim": 1536 if enabled else 0},
        }), encoding="utf-8")
        config = root / "flywheel.yaml"
        config.write_text(yaml.safe_dump({
            "schema": "robot_teleop.flywheel-config/v1",
            "storage": {"data_root": "data", "run_root": "runs", "model_cache": "cache"},
            "processing": {"derived_name": "flywheel_v1", "arm": "right", "source_domain": "real",
                            "expert_action_field": "master_joint_raw", "quality_gate": "gate.yaml"},
            "vlm": {"enabled": enabled},
            "training": {"model_config": str(model), "model_config_no_vlm": str(model)},
        }), encoding="utf-8")
        (root / "gate.yaml").write_text("{}\n", encoding="utf-8")
        return config

    def test_accepts_matching_visual_contract(self):
        self.assertEqual(load_flywheel_config(self._write(True), Path(tempfile.mkdtemp())).vlm["enabled"], True)
        self.assertEqual(load_flywheel_config(self._write(False), Path(tempfile.mkdtemp())).vlm["enabled"], False)

    def test_rejects_mismatched_visual_contract(self):
        config = self._write(True)
        payload = yaml.safe_load(config.read_text())
        model = Path(payload["training"]["model_config"])
        model.write_text(yaml.safe_dump({"model": {"visual_dim": 0}}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "VLM enabled requires"):
            load_flywheel_config(config, Path(tempfile.mkdtemp()))


if __name__ == "__main__":
    unittest.main()
