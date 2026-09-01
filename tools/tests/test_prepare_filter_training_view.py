import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PrepareFilterTrainingViewTest(unittest.TestCase):
    def test_script_help_declares_explicit_expert_action_field(self):
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/prepare_filter_training_view.sh"), "--help"],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--expert-action-field", result.stderr)

    def test_script_does_not_reference_third_party_sdk(self):
        source = (ROOT / "scripts/prepare_filter_training_view.sh").read_text(encoding="utf-8")
        self.assertNotIn("third_party", source)


if __name__ == "__main__":
    unittest.main()
