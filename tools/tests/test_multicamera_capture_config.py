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

    def test_capture_defaults_are_configurable(self):
        config = (ROOT / "config/capture_session.env").read_text(encoding="utf-8")
        launcher = (ROOT / "scripts/start_capture_session.sh").read_text(encoding="utf-8")
        for key in ("CAPTURE_SESSION", "CAPTURE_DURATION_S", "CAPTURE_CAMERA_NAMESPACE", "CAPTURE_WIDTH", "CAPTURE_FPS"):
            self.assertIn(key, config)
            self.assertIn(key, launcher)

    def test_hand_launcher_has_config_entrypoint(self):
        source = (ROOT / "scripts/start_hand_control_session.sh").read_text(encoding="utf-8")
        self.assertIn("config/hands/o6_control.env", source)
        self.assertIn("HAND_CAN_INTERFACE", source)
        self.assertIn("--config=", source)

    def test_launcher_checks_actual_python_recorder(self):
        source = (ROOT / "scripts/start_capture_session.sh").read_text(encoding="utf-8")
        self.assertIn("tools/capture_episode.py", source)

    def test_rgb_viewers_use_ros_system_python_and_configured_topics(self):
        source = (ROOT / "scripts/start_capture_session.sh").read_text(encoding="utf-8")
        self.assertIn('RQT_IMAGE_VIEW_EXEC="$(ros2 pkg prefix rqt_image_view)/lib/rqt_image_view/rqt_image_view"', source)
        self.assertIn('exec \\"$SYSTEM_PYTHON\\" \\"$RQT_IMAGE_VIEW_EXEC\\"', source)
        self.assertIn('${CAMERA_NAMESPACE%/}/color/image_raw', source)
        self.assertIn('${SECOND_CAMERA_NAMESPACE%/}/color/image_raw', source)
        self.assertNotIn("ros2 run rqt_image_view rqt_image_view", source)

    def test_launcher_refreshes_tmux_gui_environment(self):
        source = (ROOT / "scripts/start_capture_session.sh").read_text(encoding="utf-8")
        for variable in ("DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR", "WAYLAND_DISPLAY"):
            self.assertIn(variable, source)
        self.assertIn('tmux set-environment -t "$SESSION"', source)

    def test_stop_launcher_does_not_global_kill_by_process_pattern(self):
        source = (ROOT / "scripts/stop_capture_session.sh").read_text(encoding="utf-8")
        self.assertIn("tmux list-panes -s -t", source)
        self.assertNotIn("for pattern in 'ros2 bag record'", source)
        self.assertIn("another user's camera/viewer process", source)


if __name__ == "__main__":
    unittest.main()
