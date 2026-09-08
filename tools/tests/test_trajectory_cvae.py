#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

import torch
import numpy as np
import tempfile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from teleop_filter import (  # noqa: E402
    ConditionalTrajectoryVAE,
    TrajectoryFilterConfig,
    bounded_residual_command,
    trajectory_vae_loss,
    TrajectoryFilterRuntime,
    unroll_rate_limited_gain,
)


class TrajectoryCVAEModelTest(unittest.TestCase):
    def test_forward_loss_and_prior_only_inference(self):
        torch.manual_seed(7)
        config = TrajectoryFilterConfig(
            action_dim=3, state_dim=3, history_length=4, horizon=1,
            latent_dim=2, model_dim=16, num_heads=4, num_layers=1, dropout=0.0,
        )
        model = ConditionalTrajectoryVAE(config)
        commands = torch.randn(5, 4, 3)
        states = torch.randn(5, 4, 3)
        targets = torch.randn(5, 1, 3)
        outputs = model(commands, states, targets)
        losses = trajectory_vae_loss(outputs, targets)
        self.assertEqual(tuple(outputs["prediction"].shape), (5, 1, 3))
        self.assertTrue(torch.isfinite(losses["total"]))
        inference = model.predict(commands, states)
        self.assertEqual(tuple(inference["prediction"].shape), (5, 1, 3))
        self.assertEqual(tuple(inference["latent_variance"].shape), (5,))

    def test_residual_is_bounded(self):
        teleop = torch.tensor([[0.0, 0.2]])
        predicted_residual = torch.tensor([[1.0, -1.0]])
        command, correction = bounded_residual_command(
            teleop, predicted_residual, blend=0.5, max_correction_rad=0.1
        )
        self.assertTrue(torch.all(correction.abs() <= 0.1))
        self.assertTrue(torch.allclose(command, torch.tensor([[0.05, 0.15]])))

    def test_residual_is_not_reinterpreted_as_absolute_action(self):
        teleop = torch.tensor([[0.4, -0.2]])
        predicted_residual = torch.tensor([[0.02, 0.01]])
        command, correction = bounded_residual_command(
            teleop, predicted_residual, blend=1.0, max_correction_rad=0.1
        )
        self.assertTrue(torch.allclose(correction, predicted_residual))
        self.assertTrue(torch.allclose(command, torch.tensor([[0.42, -0.19]])))

    def test_visual_embedding_history_is_fused(self):
        config = TrajectoryFilterConfig(
            action_dim=2, state_dim=2, visual_dim=3, history_length=4,
            horizon=1, latent_dim=2, model_dim=16, num_heads=4, num_layers=1, dropout=0.0,
        )
        model = ConditionalTrajectoryVAE(config)
        commands = torch.randn(2, 4, 2)
        states = torch.randn(2, 4, 2)
        visuals = torch.randn(2, 4, 3)
        targets = torch.randn(2, 1, 2)
        output = model(commands, states, targets, visual=visuals)
        self.assertEqual(tuple(output["prediction"].shape), (2, 1, 2))
        with self.assertRaises(ValueError):
            model.predict(commands, states)

    def test_correction_gate_and_nominal_zero_loss(self):
        config = TrajectoryFilterConfig(
            action_dim=2, state_dim=2, history_length=3, horizon=1,
            latent_dim=2, model_dim=8, num_heads=2, num_layers=1,
            dropout=0.0, gate_enabled=True,
        )
        model = ConditionalTrajectoryVAE(config)
        commands = torch.zeros(4, 3, 2)
        states = torch.zeros(4, 3, 2)
        targets = torch.zeros(4, 1, 2)
        outputs = model(commands, states, targets)
        losses = trajectory_vae_loss(
            outputs, targets, correction_mask=torch.tensor([[0.0], [1.0], [0.0], [1.0]]),
            gate_weight=0.5, zero_weight=0.1, raw_commands=torch.zeros(4, 1, 2),
            target_mean=torch.zeros(1, 1, 2), target_std=torch.ones(1, 1, 2),
        )
        self.assertIn("gate", losses)
        self.assertIn("zero_residual", losses)
        self.assertTrue(torch.isfinite(losses["total"]))
        self.assertEqual(tuple(model.predict(commands, states)["correction_probability"].shape), (4, 1))

    def test_continuous_gain_is_rate_limited_and_recurrent(self):
        config = TrajectoryFilterConfig(
            action_dim=2, state_dim=2, history_length=3, horizon=1,
            latent_dim=2, model_dim=8, num_heads=2, num_layers=1,
            dropout=0.0, gain_enabled=True, alpha_max=0.6, alpha_rate=0.1,
        )
        model = ConditionalTrajectoryVAE(config)
        with torch.no_grad():
            model.gain_head.weight.zero_()
            model.gain_head.bias.fill_(10.0)
        commands = torch.zeros(2, 3, 2)
        states = torch.zeros(2, 3, 2)
        first = model.predict(
            commands, states, previous_alpha=torch.tensor([[0.55], [0.0]]),
            current_command=commands[:, -1],
        )
        self.assertTrue(torch.all(first["gain_delta"] <= config.alpha_rate))
        self.assertTrue(torch.allclose(first["alpha"], torch.tensor([[0.6], [0.1]]), atol=1e-4))

    def test_gain_loss_supervises_raise_and_release(self):
        prediction = torch.zeros(2, 1, 2)
        common = {
            "prediction": prediction,
            "posterior_mean": torch.zeros(2, 1),
            "posterior_log_variance": torch.zeros(2, 1),
            "prior_mean": torch.zeros(2, 1),
            "prior_log_variance": torch.zeros(2, 1),
            "gate_logits": None,
        }
        labels = torch.tensor([[1.0], [0.0]])
        good = trajectory_vae_loss(
            {**common, "alpha": torch.tensor([[0.6], [0.0]])}, prediction,
            correction_mask=labels, gain_weight=1.0, alpha_max=1.0,
        )
        wrong = trajectory_vae_loss(
            {**common, "alpha": torch.tensor([[0.0], [0.6]])}, prediction,
            correction_mask=labels, gain_weight=1.0, alpha_max=1.0,
        )
        self.assertLess(good["gain"], wrong["gain"])

    def test_gain_unroll_resets_at_episode_boundaries(self):
        desired = torch.tensor([[0.8], [0.8], [0.0], [0.8]])
        alpha = unroll_rate_limited_gain(
            desired, torch.tensor([True, False, False, True]), alpha_rate=0.1,
        )
        self.assertTrue(torch.allclose(alpha, torch.tensor([[0.1], [0.2], [0.1], [0.1]])))

    def test_shared_action_gain_decoder_outputs_both(self):
        config = TrajectoryFilterConfig(
            action_dim=2, state_dim=2, history_length=3, horizon=4,
            latent_dim=2, model_dim=8, num_heads=2, num_layers=1,
            dropout=0.0, gain_enabled=True, gain_current_command=True,
            shared_action_gain_head=True,
        )
        model = ConditionalTrajectoryVAE(config)
        commands = torch.zeros(2, 3, 2)
        states = torch.zeros(2, 3, 2)
        result = model.predict(commands, states, current_command=commands[:, -1])
        self.assertEqual(tuple(result["prediction"].shape), (2, 4, 2))
        self.assertEqual(tuple(result["desired_gain"].shape), (2, 1))

    def test_fixed_gain_is_rate_limited(self):
        config = TrajectoryFilterConfig(
            action_dim=2, state_dim=2, history_length=3, horizon=2,
            latent_dim=2, model_dim=8, num_heads=2, num_layers=1,
            dropout=0.0, gain_enabled=True, gain_current_command=True,
            alpha_rate=0.1, fixed_gain=0.4,
        )
        model = ConditionalTrajectoryVAE(config)
        commands = torch.zeros(1, 3, 2)
        states = torch.zeros(1, 3, 2)
        result = model.predict(commands, states, current_command=commands[:, -1])
        self.assertTrue(torch.allclose(result["desired_gain"], torch.tensor([[0.4]])))
        self.assertTrue(torch.allclose(result["alpha"], torch.tensor([[0.1]])))

    def test_checkpoint_runtime_normalizes_and_bounds(self):
        config = TrajectoryFilterConfig(
            action_dim=2, state_dim=2, history_length=3, horizon=1,
            latent_dim=2, model_dim=8, num_heads=2, num_layers=1, dropout=0.0,
        )
        model = ConditionalTrajectoryVAE(config)
        stats = {
            name: {"mean": np.zeros((1, 1, 2), dtype=np.float32), "std": np.ones((1, 1, 2), dtype=np.float32)}
            for name in ("commands", "states", "targets")
        }
        checkpoint = {
            "schema": "robot_teleop.trajectory-filter-checkpoint/v0.1",
            "model_config": config.to_dict(),
            "model_state": model.state_dict(),
            "normalization": stats,
            "runtime": {
                "deterministic_prior": True, "blend": 0.5,
                "max_correction_rad": 0.02, "deployment": "offline_and_simulation_only",
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "filter.pt"
            torch.save(checkpoint, path)
            runtime = TrajectoryFilterRuntime.load(path)
            result = runtime.predict(
                np.zeros((4, 3, 2), dtype=np.float32),
                np.zeros((4, 3, 2), dtype=np.float32),
                current_command=np.full((4, 2), 0.25, dtype=np.float32),
            )
        self.assertEqual(result.predicted_residuals.shape, (4, 1, 2))

    def test_visual_checkpoint_runtime_requires_and_uses_visual_history(self):
        config = TrajectoryFilterConfig(
            action_dim=2, state_dim=2, visual_dim=3, history_length=3, horizon=1,
            latent_dim=2, model_dim=8, num_heads=2, num_layers=1, dropout=0.0,
        )
        model = ConditionalTrajectoryVAE(config)
        stats = {
            name: {"mean": np.zeros((1, 1, size), dtype=np.float32), "std": np.ones((1, 1, size), dtype=np.float32)}
            for name, size in (("commands", 2), ("states", 2), ("targets", 2), ("visuals", 3))
        }
        checkpoint = {
            "schema": "robot_teleop.trajectory-filter-checkpoint/v0.1",
            "model_config": config.to_dict(), "model_state": model.state_dict(),
            "normalization": stats,
            "visual_encoder": {
                "model_id": "test-vlm", "model_revision": "commit-1",
                "camera_ids": ["main_rgb"], "embedding_dim": 3,
            },
            "runtime": {"deterministic_prior": True, "deployment": "offline_and_simulation_only"},
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "filter.pt"
            torch.save(checkpoint, path)
            runtime = TrajectoryFilterRuntime.load(path)
            commands = np.zeros((4, 3, 2), dtype=np.float32)
            states = np.zeros((4, 3, 2), dtype=np.float32)
            visuals = np.zeros((4, 3, 3), dtype=np.float32)
            result = runtime.predict(commands, states, visuals=visuals)
            self.assertEqual(result.predicted_residuals.shape, (4, 1, 2))
            with self.assertRaises(ValueError):
                runtime.predict(commands, states)


if __name__ == "__main__":
    unittest.main()
