import unittest

from tools.audit_filter_step_rate import summarize_rows


class FilterStepRateAuditTest(unittest.TestCase):
    def test_infers_50hz_history_and_horizon_duration(self) -> None:
        rows = [
            {"episode_id": "e", "timestamp_ns": index * 20_000_000}
            for index in range(100)
        ]
        report = summarize_rows(rows, runtime_hz=5.0)
        self.assertAlmostEqual(report["median_hz"], 50.0)
        self.assertAlmostEqual(report["history_seconds_at_median"], 0.32)
        self.assertAlmostEqual(report["horizon_seconds_at_median"], 0.16)
        self.assertAlmostEqual(report["runtime_history_seconds"], 3.2)
        self.assertAlmostEqual(report["time_scale_ratio"], 10.0)

    def test_separates_episode_ids(self) -> None:
        rows = [
            {"episode_id": "a", "timestamp_ns": 0},
            {"episode_id": "a", "timestamp_ns": 20_000_000},
            {"episode_id": "b", "timestamp_ns": 0},
            {"episode_id": "b", "timestamp_ns": 200_000_000},
        ]
        report = summarize_rows(rows)
        self.assertEqual(len(report["episodes"]), 2)


if __name__ == "__main__":
    unittest.main()
