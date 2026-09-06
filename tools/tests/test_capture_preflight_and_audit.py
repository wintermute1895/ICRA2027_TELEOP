#!/usr/bin/env python3
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("capture_preflight", ROOT / "scripts/preflight.py")
PREFLIGHT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PREFLIGHT)


class CapturePreflightAndAuditTest(unittest.TestCase):
    def test_real_capture_topics_include_causal_chain_and_tactile(self):
        topics = PREFLIGHT.capture_topics("real", ("right",), True)
        self.assertIn("/teleop/right/master_joint_raw", topics)
        self.assertIn("/teleop/right/master_joint_filtered", topics)
        self.assertIn("/teleop/right/mapped_joint_command", topics)
        self.assertIn("/robot1/right_arm/vendor_command", topics)
        self.assertIn("/robot1/right_arm/joint_states", topics)
        self.assertIn("/cb_right_hand_matrix_touch_mass", topics)

    def test_samples_are_opt_in(self):
        source = (ROOT / "scripts/preflight.py").read_text(encoding="utf-8")
        self.assertIn("--require-samples", source)

    def test_terminal_audit_is_explicit_and_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "audit.json"
            command = [sys.executable, str(ROOT / "tools/finalize_episode_audit.py"), "--output", str(output), "--episode-id", "e1", "--success", "--termination-reason", "verified"]
            subprocess.run(command, check=True, text=True, capture_output=True)
            audit = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(audit["success"])
            self.assertEqual(audit["audit_source"], "manual_structured")
            duplicate = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(duplicate.returncode, 0)


if __name__ == "__main__":
    unittest.main()
