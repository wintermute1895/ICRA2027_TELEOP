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

    def test_config_parses_model_deployment_confirmation(self) -> None:
        os.environ["TELEOP_CAP_LEARNED_FILTER_CONFIG"] = "/tmp/filter-promoted.yaml"
        os.environ["TELEOP_CAP_MODEL_DEPLOYMENT_CONFIG"] = "/tmp/model-deployment.yaml"
        os.environ["TELEOP_CAP_MODEL_DEPLOYMENT_CONFIRM"] = (
            "I_UNDERSTAND_MODEL_DEPLOYMENT"
        )
        config = manager.ManagerConfig.from_env()
        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(
            config.model_deployment_confirm,
            "I_UNDERSTAND_MODEL_DEPLOYMENT",
        )

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


class CameraPreviewImageTest(unittest.TestCase):
    class _Image:
        pass

    @staticmethod
    def _message(encoding: str, data: bytes, width: int = 2, height: int = 2) -> object:
        message = CameraPreviewImageTest._Image()
        message.encoding = encoding
        message.data = data
        message.width = width
        message.height = height
        message.step = width * len(data) // (width * height) if width and height else len(data)
        return message

    def test_decode_rgb8_and_bgr8(self) -> None:
        rgb = CameraPreviewImageTest._message(
            "rgb8",
            bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255]),
        )
        frame = manager._preview_rgb_image(rgb)
        self.assertIsNotNone(frame)
        assert frame is not None
        self.assertEqual(frame[0, 0].tolist(), [255, 0, 0])
        self.assertEqual(frame[0, 1].tolist(), [0, 255, 0])

        bgr = CameraPreviewImageTest._message(
            "bgr8",
            bytes([0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255]),
        )
        frame = manager._preview_rgb_image(bgr)
        self.assertIsNotNone(frame)
        assert frame is not None
        self.assertEqual(frame[0, 0].tolist(), [255, 0, 0])
        self.assertEqual(frame[0, 1].tolist(), [0, 255, 0])

    def test_unsupported_encoding_returns_none(self) -> None:
        message = CameraPreviewImageTest._message("unsupported", b"x")
        self.assertIsNone(manager._preview_rgb_image(message))


if __name__ == "__main__":
    unittest.main()
