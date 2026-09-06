import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_event_recorder import append_event, event_for_key, load_state


class AuditEventRecorderTest(unittest.TestCase):
    def test_rejects_key_without_active_episode(self) -> None:
        event, active = event_for_key(
            "1", {"active": False}, auditor_id="a1", sequence=1,
            correction_active=False, ros_time_ns=123,
        )
        self.assertIsNone(event)
        self.assertFalse(active)

    def test_toggle_and_durable_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = {"active": True, "episode_id": "ep-1", "run_dir": str(root)}
            start, active = event_for_key(
                "4", state, auditor_id="a1", sequence=1,
                correction_active=False, ros_time_ns=123,
            )
            self.assertEqual(start["event_type"], "correction_start")
            self.assertTrue(active)
            stop, active = event_for_key(
                "4", state, auditor_id="a1", sequence=2,
                correction_active=active, ros_time_ns=456,
            )
            self.assertEqual(stop["event_type"], "correction_end")
            self.assertFalse(active)
            path = append_event(root, start)
            append_event(root, stop)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([row["timestamp_ns"] for row in rows], [123, 456])

    def test_invalid_state_is_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            path.write_text("not-json")
            self.assertFalse(load_state(path)["active"])


if __name__ == "__main__":
    unittest.main()
