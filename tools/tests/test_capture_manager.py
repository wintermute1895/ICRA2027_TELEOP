import os
import unittest

from tools import capture_manager as manager


REQUIRED_ENV = {
    "TELEOP_CAP_ROOT_DIR": "/tmp/repo",
    "TELEOP_CAP_RUN_ROOT": "/tmp/data",
    "TELEOP_CAP_SESSION": "teleop_capture",
    "TELEOP_CAP_CAMERA_SERIAL": "261722075670",
    "TELEOP_CAP_CAMERA_NAMESPACE": "/camera/camera",
    "TELEOP_CAP_SYSTEM_PYTHON": "/usr/bin/python3",
    "TELEOP_CAP_RUNEVIDENCE_PYTHON": "/opt/runevidence/bin/python3",
    "TELEOP_CAP_RUNEVIDENCE_BIN": "/opt/runevidence/bin/runevidence",
}


class SetEnvMixin:
    def setUp(self) -> None:
        self.old = {key: os.environ.get(key) for key in list(os.environ)}
        os.environ.update(REQUIRED_ENV)

    def tearDown(self) -> None:
        for key in list(os.environ):
            os.environ.pop(key, None)
        for key, value in self.old.items():
            if value is not None:
                os.environ[key] = value


class CaptureManagerConfigTest(SetEnvMixin, unittest.TestCase):
    def test_config_parses_dual_cameras(self) -> None:
        os.environ["TELEOP_CAP_SECOND_CAMERA_SERIAL"] = "327122074150"
        os.environ["TELEOP_CAP_SECOND_CAMERA_NAMESPACE"] = "/camera2/camera"
        config = manager.ManagerConfig.from_env()
        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.camera_namespaces, "/camera/camera,/camera2/camera")

    def test_manual_recorder_command_has_no_auto_start(self) -> None:
        config = manager.ManagerConfig.from_env()
        assert config is not None
        session = manager.CaptureSession(config)
        command = session.build_recorder_command()
        self.assertNotIn("--auto-start", command)
        self.assertIn("--runs-root", command)
        self.assertIn(str(config.root_dir / "tools/capture_episode.py"), command)

    def test_timed_recorder_command_adds_max_duration(self) -> None:
        os.environ["TELEOP_CAP_CAPTURE_MODE"] = "timed"
        os.environ["TELEOP_CAP_DURATION_S"] = "15"
        config = manager.ManagerConfig.from_env()
        assert config is not None
        session = manager.CaptureSession(config)
        command = session.build_recorder_command()
        self.assertIn("--auto-start", command)
        self.assertIn("--max-duration", command)

    def test_strip_ansi_keeps_text(self) -> None:
        self.assertEqual(manager.strip_ansi(b"\x1b[31mREC\x1b[0m"), "REC")


if __name__ == "__main__":
    unittest.main()
