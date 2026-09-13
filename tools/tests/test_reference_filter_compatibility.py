"""Compatibility checks for the archived formal-reference filter checkpoints."""
from __future__ import annotations

import base64
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from teleop_filter.runtime import TrajectoryFilterRuntime  # noqa: E402
from learned_filter_worker import Worker  # noqa: E402


REFERENCE_ROOT = ROOT / "artifacts" / "filter_reference_20260910" / "checkpoints"


@unittest.skipUnless(REFERENCE_ROOT.is_dir(), "reference checkpoint archive is not present")
class ReferenceFilterCompatibilityTest(unittest.TestCase):
    def test_reference_models_load_and_predict(self) -> None:
        checkpoints = sorted(REFERENCE_ROOT.glob("*/*.pt"))
        self.assertEqual(len(checkpoints), 12)
        rng = np.random.default_rng(7)
        commands = rng.normal(size=(1, 16, 14)).astype(np.float32)
        states = rng.normal(size=(1, 16, 7)).astype(np.float32)
        visuals = rng.normal(size=(1, 16, 1536)).astype(np.float32)
        current_command = rng.normal(size=(1, 7)).astype(np.float32)

        for checkpoint in checkpoints:
            with self.subTest(checkpoint=str(checkpoint.relative_to(REFERENCE_ROOT))):
                runtime = TrajectoryFilterRuntime.load(checkpoint, device="cpu")
                self.assertEqual(runtime.target_semantics, "delta_from_last_executed")
                self.assertEqual(runtime.command_semantics, "raw_and_executed_action_history")
                prediction = runtime.predict(
                    commands,
                    states,
                    visuals=visuals,
                    current_command=current_command,
                    previous_alpha=0.0,
                )
                self.assertEqual(prediction.predicted_actions.shape, (1, 8, 7))
                self.assertEqual(prediction.predicted_residuals.shape, (1, 8, 7))
                self.assertTrue(np.isfinite(prediction.predicted_actions).all())
                self.assertTrue(np.isfinite(prediction.predicted_residuals).all())
                self.assertIsNotNone(prediction.alpha)
                self.assertEqual(float(prediction.alpha[0, 0]), 0.0)

    @staticmethod
    def _worker_config(checkpoint: Path, **overrides: object) -> dict:
        config = {
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            "device": "cpu",
            "model_cache": "/tmp/unused-vlm-cache",
            "inference_hz": 5.0,
            "execution_mode": "receding_horizon",
            "safety": {
                "joint_min_rad": [-1.0] * 7,
                "joint_max_rad": [1.0] * 7,
                "max_residual_rad": 0.01,
                "max_residual_rate_rad_s": 0.05,
                "max_command_velocity_rad_s": 0.5,
                "max_model_age_ms": 300.0,
            },
            "cameras": [{"id": "main_rgb"}, {"id": "auxiliary_rgb"}],
        }
        config.update(overrides)
        return config

    @staticmethod
    def _request() -> dict:
        return {
            "timestamp_ns": 1,
            "master_joint_raw_rad": [0.0] * 7,
            "robot_joint_state_rad": [0.0] * 7,
            "camera_jpeg_base64": {
                "main_rgb": base64.b64encode(b"x").decode(),
                "auxiliary_rgb": base64.b64encode(b"x").decode(),
            },
        }

    @patch("learned_filter_worker.OnlineVisualEncoder")
    def test_reference_worker_outputs_zero_authority(self, encoder_class) -> None:
        checkpoint = REFERENCE_ROOT / "button" / "cvae_seed7.pt"
        encoder = encoder_class.return_value
        encoder.encode_jpegs.return_value = np.zeros(1536, dtype=np.float32)
        worker = Worker(self._worker_config(checkpoint))
        request = self._request()
        response = None
        for index in range(17):
            request["timestamp_ns"] = (index + 1) * 200_000_000
            response = worker.handle(request)
        assert response is not None
        self.assertTrue(response["ready"])
        self.assertEqual(response["alpha"], 0.0)
        self.assertEqual(response["residual_rad"], [0.0] * 7)
        self.assertEqual(response["command_rad"], [0.0] * 7)

    @patch("learned_filter_worker.OnlineVisualEncoder")
    def test_worker_reuses_embedding_until_camera_frame_changes(self, encoder_class) -> None:
        checkpoint = REFERENCE_ROOT / "button" / "cvae_seed7.pt"
        encoder = encoder_class.return_value
        encoder.encode_jpegs.return_value = np.ones(1536, dtype=np.float32)
        worker = Worker(self._worker_config(checkpoint))
        request = self._request()
        request["camera_stamp_ns"] = {"main_rgb": 1, "auxiliary_rgb": 1}
        worker.handle(request)
        worker.handle(request)
        self.assertEqual(encoder.encode_jpegs.call_count, 1)
        request["camera_stamp_ns"] = {"main_rgb": 2, "auxiliary_rgb": 2}
        worker.handle(request)
        self.assertEqual(encoder.encode_jpegs.call_count, 2)

    @patch("learned_filter_worker.OnlineVisualEncoder")
    def test_reference_worker_supports_fixed_authority_selection(self, encoder_class) -> None:
        checkpoint = REFERENCE_ROOT / "button" / "cvae_seed7.pt"
        encoder = encoder_class.return_value
        encoder.encode_jpegs.return_value = np.ones(1536, dtype=np.float32)
        worker = Worker(self._worker_config(
            checkpoint,
            authority={"mode": "fixed", "gain": 0.10},
        ))
        request = self._request()
        response = None
        for index in range(17):
            request["timestamp_ns"] = (index + 1) * 200_000_000
            response = worker.handle(request)
        assert response is not None
        self.assertTrue(response["ready"])
        self.assertEqual(response["alpha"], 0.10)
        self.assertGreater(max(abs(value) for value in response["residual_rad"]), 0.0)
        self.assertEqual(response["command_rad"], response["residual_rad"])


if __name__ == "__main__":
    unittest.main()
