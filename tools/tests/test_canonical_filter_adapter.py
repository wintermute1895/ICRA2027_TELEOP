#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from canonical_episode_to_filter_jsonl import admitted  # noqa: E402


class CanonicalFilterAdapterTest(unittest.TestCase):
    def _manifest(self, buffer: str = "A_action") -> dict:
        return {
            "schema_version": "teleop_episode/v0.1",
            "intended_uses": ["filter_training"],
            "terminal_audit": {
                "buffer": buffer,
                "success": True,
                "safety_violation": False,
                "unlogged_external_override": False,
            },
            "data_integrity": {
                "complete_causal_record": True,
                "synchronization_valid": True,
            },
        }

    def test_only_a_action_is_admitted(self):
        self.assertTrue(admitted(self._manifest()))
        self.assertFalse(admitted(self._manifest("A_audit")))


if __name__ == "__main__":
    unittest.main()
