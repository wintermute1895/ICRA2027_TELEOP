#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

try:
    from export_rosbag_episode import deduplicate_state_samples, filter_stage_coverage
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

    def test_filter_stage_coverage_requires_all_six_stages(self):
        complete = {name: 1 for name in ("raw_action_rad", "candidate_action_rad",
            "correction_probability", "learned_gain", "composed_action_rad", "issued_action_rad")}
        complete["filter_inference_stamps_aligned"] = True
        incomplete = dict(complete, learned_gain=None)
        result = filter_stage_coverage([complete, incomplete])
        self.assertEqual(result["candidate_rows"], 2)
        self.assertEqual(result["complete_candidate_rows"], 1)
        self.assertEqual(result["complete_candidate_ratio"], 0.5)
        self.assertEqual(result["timestamp_aligned_candidate_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
