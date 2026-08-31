#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

try:
    from export_rosbag_episode import deduplicate_state_samples
except ModuleNotFoundError as error:
    if error.name in {"rclpy", "rosbag2_py", "rosidl_runtime_py"}:
        deduplicate_state_samples = None
    else:
        raise


@unittest.skipIf(deduplicate_state_samples is None, "ROS2 Python modules are unavailable")
class ExportTimestampPolicyTest(unittest.TestCase):
    def test_keeps_latest_receipt_for_duplicate_header_stamp(self):
        older, latest, next_sample = object(), object(), object()
        samples = [(20, 200, next_sample), (10, 101, latest), (10, 100, older)]
        unique, dropped = deduplicate_state_samples(samples)
        self.assertEqual(unique, [(10, 101, latest), (20, 200, next_sample)])
        self.assertEqual(dropped, 1)


if __name__ == "__main__":
    unittest.main()
