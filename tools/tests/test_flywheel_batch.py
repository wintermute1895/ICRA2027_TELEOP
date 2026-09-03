import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from run_flywheel_batch import eligible_runs  # noqa: E402


class FlywheelBatchTest(unittest.TestCase):
    def _run(self, root: Path, name: str, *, success=True, safety=False, override=False, events=True):
        run = root / "evidence" / "teleop" / name
        artifacts = run / "artifacts" / "rosbag2"
        artifacts.mkdir(parents=True)
        (artifacts / "metadata.yaml").write_text("rosbag2_bagfile_information: {}\n")
        (run / "artifacts" / "teleop_capture_manifest.json").write_text("{}")
        (run / "artifacts" / "terminal_audit.json").write_text(json.dumps({
            "success": success,
            "safety_violation": safety,
            "unlogged_external_override": override,
        }))
        if events:
            (run / "artifacts" / "audit_events.jsonl").write_text("{}\n")

    def test_selector_uses_technical_outcome_not_task_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root, "arbitrary-task-label")
            self._run(root, "failed", success=False)
            self._run(root, "unsafe", safety=True)
            self._run(root, "override", override=True)
            names = [path.name for path in eligible_runs(root)]
            self.assertEqual(names, ["arbitrary-task-label"])


if __name__ == "__main__":
    unittest.main()
