#!/usr/bin/env python3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class MultiCameraCaptureConfigTest(unittest.TestCase):
    def test_recorder_uses_camera_namespace_list(self):
        source = (ROOT / "scripts/record_episode.sh").read_text(encoding="utf-8")
        self.assertIn('CAMERA_NAMESPACES="${CAMERA_NAMESPACES:-$CAMERA_NAMESPACE}"', source)
        self.assertIn('"${camera}/color/image_raw"', source)
        self.assertIn('"${camera}/aligned_depth_to_color/image_raw"', source)

    def test_launcher_has_explicit_second_camera_serial(self):
        source = (ROOT / "scripts/start_capture_session.sh").read_text(encoding="utf-8")
        self.assertIn("--second-camera-serial", source)
        self.assertIn("SECOND_CAMERA_SERIAL", source)
        self.assertIn("camera2", source)

    def test_launcher_supports_manual_episode_segments(self):
        launcher = (ROOT / "scripts/start_capture_session.sh").read_text(encoding="utf-8")
        recorder = (ROOT / "scripts/record_episode.sh").read_text(encoding="utf-8")
        self.assertIn("--manual-segments", launcher)
        self.assertIn("ros2 bag reindex", recorder)
        self.assertNotIn('wait "$wait_pid"', recorder)
        self.assertIn('TELEOP_CAPTURE_MODE=$CAPTURE_MODE', launcher)
        self.assertIn('CAPTURE_MODE="${TELEOP_CAPTURE_MODE:-timed}"', recorder)
        self.assertIn("回车结束并保存本条数据", recorder)
        self.assertIn("tools/capture_episode.py", launcher)
        capture = (ROOT / "tools/capture_episode.py").read_text(encoding="utf-8")
        self.assertIn("exist_ok=True", capture)
        self.assertNotIn("bag_dir.mkdir(parents=True)", capture)
        self.assertIn("write_report(run_dir); write_analysis(run_dir); build_manifest(run_dir)", capture)
        self.assertIn('bag_dir.glob("*.db3.zstd")', capture)
        self.assertIn('terminal-audit/v0.1', capture)
        self.assertIn('audit_deferred', capture)

    def test_real_launcher_checks_can_before_starting_nodes(self):
        source = (ROOT / "scripts/start_capture_session.sh").read_text(encoding="utf-8")
        self.assertIn("no SocketCAN canN interface detected", source)
        self.assertIn("operstate", source)
        self.assertIn("enable_all_can.sh --confirm ENABLE_ALL_CAN_INTERFACES", source)

    def test_manifest_experiment_id_is_not_overwritten_by_profile(self):
        source = (ROOT / "scripts/start_capture_session.sh").read_text(encoding="utf-8")
        self.assertIn('if [[ -z "$EXPERIMENT_MANIFEST" ]]; then', source)


if __name__ == "__main__":
    unittest.main()
