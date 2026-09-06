import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.promote_runtime_model import main
from tools.model_artifacts import sha256_path


class PromoteRuntimeModelTest(unittest.TestCase):
    def test_filter_config_gets_checkpoint_and_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint = root / "model.pt"
            checkpoint.write_bytes(b"checkpoint")
            template = root / "template.yaml"
            template.write_text(
                "schema: robot_teleop.learned-filter-runtime/v1\n"
                "enabled: false\ncheckpoint: ''\ncheckpoint_sha256: ''\n",
                encoding="utf-8",
            )
            output = root / "runtime.yaml"
            import sys
            old = sys.argv
            try:
                sys.argv = ["promote", "--kind", "filter", "--checkpoint", str(checkpoint), "--template", str(template), "--output", str(output)]
                self.assertEqual(main(), 0)
            finally:
                sys.argv = old
            text = output.read_text(encoding="utf-8")
            self.assertIn("enabled: true", text)
            self.assertIn(hashlib.sha256(b"checkpoint").hexdigest(), text)

    def test_directory_artifact_hash_is_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "b").write_bytes(b"b")
            (root / "a").write_bytes(b"a")
            first = sha256_path(root)
            (root / "a").write_bytes(b"a2")
            self.assertNotEqual(first, sha256_path(root))


if __name__ == "__main__":
    unittest.main()
