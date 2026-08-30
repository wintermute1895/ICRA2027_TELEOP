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


if __name__ == "__main__":
    unittest.main()
