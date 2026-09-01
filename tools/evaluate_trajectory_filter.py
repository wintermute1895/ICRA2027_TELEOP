#!/usr/bin/env python3
"""Evaluate a trajectory-filter checkpoint without ROS or hardware access."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from teleop_filter import TrajectoryFilterRuntime  # noqa: E402
from train_trajectory_filter import build_windows  # noqa: E402


def metrics(prediction: np.ndarray, target: np.ndarray) -> dict[str, float]:
    error = prediction - target
    return {
        "mae_rad": float(np.abs(error).mean()),
        "rmse_rad": float(np.sqrt(np.square(error).mean())),
        "first_step_mae_rad": float(np.abs(error[:, 0]).mean()),
    }


def residual_targets(windows, target_semantics: str) -> np.ndarray:
    """Return targets in the same residual space used by runtime inference.

    Training on ``recorded_expert_action`` stores absolute joint commands.  The
    runtime deliberately converts its predicted absolute action to a residual
    by subtracting the latest raw teleoperation command.  Comparing that
    residual to the absolute target would produce a plausible-looking but
    invalid error metric, so the conversion must also happen in evaluation.
    """
    if target_semantics == "recorded_expert_action":
        return windows.targets - windows.commands[:, -1:, :]
    return windows.targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--episode", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--stochastic", action="store_true", help="sample the learned prior")
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite output: {args.output_dir}")

    runtime = TrajectoryFilterRuntime.load(args.checkpoint, device=args.device)
    summaries = []
    prediction_rows = []
    absolute_error_sum = 0.0
    squared_error_sum = 0.0
    error_elements = 0
    first_absolute_error_sum = 0.0
    first_error_elements = 0
    for path in args.episode:
        windows = build_windows(
            path,
            history_length=runtime.config.history_length,
            horizon=runtime.config.horizon,
            context_dim=runtime.config.context_dim,
            visual_dim=runtime.config.visual_dim,
            action_dim=runtime.config.action_dim,
            state_dim=runtime.config.state_dim,
        )
        result = runtime.predict(
            windows.commands,
            windows.states,
            windows.contexts,
            windows.visuals,
            deterministic=not args.stochastic,
        )
        targets = residual_targets(windows, runtime.target_semantics)
        summary = {
            "episode_id": windows.episode_id,
            "source": str(path.resolve()),
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "windows": int(len(windows.targets)),
            "target_semantics": runtime.target_semantics,
            "metric_space": "residual_rad",
            **metrics(result.predicted_residuals, targets),
            "latent_variance_mean": float(result.latent_variance.mean()),
            "proposed_residual_abs_mean_rad": float(np.abs(result.predicted_residuals[:, 0]).mean()),
        }
        summaries.append(summary)
        error = result.predicted_residuals - targets
        absolute_error_sum += float(np.abs(error).sum())
        squared_error_sum += float(np.square(error).sum())
        error_elements += int(error.size)
        first_absolute_error_sum += float(np.abs(error[:, 0]).sum())
        first_error_elements += int(error[:, 0].size)
        for index in range(len(windows.targets)):
            prediction_rows.append({
                "episode_id": windows.episode_id,
                "window_index": index,
                "predicted_residual_rad": result.predicted_residuals[index, 0].tolist(),
                "target_residual_rad": targets[index, 0].tolist(),
                "latent_variance": float(result.latent_variance[index]),
            })

    total_windows = sum(item["windows"] for item in summaries)
    report = {
        "schema": "robot_teleop.trajectory-filter-evaluation/v0.1",
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        "mode": "stochastic_prior" if args.stochastic else "deterministic_prior",
        "deployment": "offline_and_simulation_only",
        "target_semantics": runtime.target_semantics,
        "metric_space": "residual_rad",
        "aggregate": {
            "episodes": len(summaries),
            "windows": total_windows,
            "mae_rad": absolute_error_sum / error_elements,
            "rmse_rad": float(np.sqrt(squared_error_sum / error_elements)),
            "first_step_mae_rad": first_absolute_error_sum / first_error_elements,
        },
        "episodes": summaries,
    }
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "evaluation_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "predictions.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in prediction_rows),
        encoding="utf-8",
    )
    print(json.dumps(report["aggregate"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
