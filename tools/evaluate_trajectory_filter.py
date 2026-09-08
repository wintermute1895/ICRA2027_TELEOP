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

from teleop_filter import TrajectoryFilterPrediction, TrajectoryFilterRuntime  # noqa: E402
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
        return windows.targets - windows.current_commands[:, None, :]
    return windows.targets


def average_precision(scores: np.ndarray, labels: np.ndarray) -> float | None:
    positives = int(labels.sum())
    if positives == 0:
        return None
    order = np.argsort(-scores, kind="stable")
    ranked = labels[order]
    precision = np.cumsum(ranked) / np.arange(1, len(ranked) + 1)
    return float((precision * ranked).sum() / positives)


def mean_available(rows: list[dict], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return None if not values else float(np.mean(values))


def predict_episode(runtime: TrajectoryFilterRuntime, windows, deterministic: bool) -> TrajectoryFilterPrediction:
    if not runtime.config.gain_enabled:
        return runtime.predict(
            windows.commands,
            windows.states,
            windows.contexts,
            windows.visuals,
            current_command=windows.current_commands,
            deterministic=deterministic,
        )
    rows = []
    previous_alpha = 0.0
    for index in range(len(windows.targets)):
        result = runtime.predict(
            windows.commands[index:index + 1], windows.states[index:index + 1],
            None if windows.contexts is None else windows.contexts[index:index + 1],
            None if windows.visuals is None else windows.visuals[index:index + 1],
            previous_alpha=previous_alpha,
            current_command=windows.current_commands[index:index + 1],
            deterministic=deterministic,
        )
        previous_alpha = float(result.alpha[0, 0])
        rows.append(result)
    combine = lambda name: None if getattr(rows[0], name) is None else np.concatenate([getattr(row, name) for row in rows])
    return TrajectoryFilterPrediction(**{
        name: combine(name) for name in (
            "predicted_actions", "predicted_residuals", "latent_variance",
            "correction_probability", "gain_delta", "alpha", "desired_gain",
        )
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--episode", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--stochastic", action="store_true", help="sample the learned prior")
    parser.add_argument("--gain-threshold", type=float, help="validation-frozen threshold for gain interval metrics")
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
        result = predict_episode(runtime, windows, deterministic=not args.stochastic)
        targets = residual_targets(windows, runtime.target_semantics)
        action_metrics = metrics(result.predicted_actions, windows.targets)
        summary = {
            "episode_id": windows.episode_id,
            "source": str(path.resolve()),
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "windows": int(len(windows.targets)),
            "target_semantics": runtime.target_semantics,
            "metric_space": "residual_rad",
            **metrics(result.predicted_residuals, targets),
            "action_mae_rad": action_metrics["mae_rad"],
            "action_rmse_rad": action_metrics["rmse_rad"],
            "latent_variance_mean": float(result.latent_variance.mean()),
            "proposed_residual_abs_mean_rad": float(np.abs(result.predicted_residuals[:, 0]).mean()),
        }
        if result.correction_probability is not None:
            probabilities = result.correction_probability[:, 0]
            labels = windows.correction_mask[:, 0]
            summary.update({
                "gate_brier": float(np.mean((probabilities - labels) ** 2)),
                "gate_accuracy_at_0_5": float(np.mean((probabilities >= 0.5) == (labels >= 0.5))),
                "correction_probability_mean": float(probabilities.mean()),
            })
        if result.alpha is not None:
            alpha = result.alpha[:, 0]
            labels = windows.correction_mask[:, 0].astype(bool)
            nominal = ~labels
            summary.update({
                "gain_correction_mean": None if not labels.any() else float(alpha[labels].mean()),
                "gain_nominal_mean": None if not nominal.any() else float(alpha[nominal].mean()),
                "gain_mean_absolute_variation": 0.0 if len(alpha) < 2 else float(np.abs(np.diff(alpha)).mean()),
                "gain_auprc": average_precision(alpha, labels.astype(np.float32)),
            })
            if args.gain_threshold is not None:
                predicted = alpha >= args.gain_threshold
                union = np.logical_or(predicted, labels).sum()
                summary["gain_interval_iou"] = None if union == 0 else float(np.logical_and(predicted, labels).sum() / union)
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
                **({"correction_probability": float(result.correction_probability[index, 0])}
                   if result.correction_probability is not None else {}),
            })

    total_windows = sum(item["windows"] for item in summaries)
    report = {
        "schema": "robot_teleop.trajectory-filter-evaluation/v0.1",
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        "mode": "stochastic_prior" if args.stochastic else "deterministic_prior",
        "deployment": "offline_and_simulation_only",
        "target_semantics": runtime.target_semantics,
        "command_semantics": runtime.command_semantics,
        "metric_space": "residual_rad",
        "aggregate": {
            "episodes": len(summaries),
            "windows": total_windows,
            "mae_rad": absolute_error_sum / error_elements,
            "rmse_rad": float(np.sqrt(squared_error_sum / error_elements)),
            "first_step_mae_rad": first_absolute_error_sum / first_error_elements,
            "action_mae_rad": mean_available(summaries, "action_mae_rad"),
            "gain_correction_mean": mean_available(summaries, "gain_correction_mean"),
            "gain_nominal_mean": mean_available(summaries, "gain_nominal_mean"),
            "gain_mean_absolute_variation": mean_available(summaries, "gain_mean_absolute_variation"),
            "gain_auprc": mean_available(summaries, "gain_auprc"),
            "gain_interval_iou": mean_available(summaries, "gain_interval_iou"),
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
