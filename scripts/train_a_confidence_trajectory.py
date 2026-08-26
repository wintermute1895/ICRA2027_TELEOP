#!/usr/bin/env python3
"""Train a light confidence-conditioned trajectory policy from A-group segments.

This is an offline model only. It never opens a ROS node or sends a command.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def quality_target(states: np.ndarray, commands: np.ndarray, fps: int) -> float:
    tracking = float(np.mean(np.abs(commands - states)))
    velocity = float(np.percentile(np.max(np.abs(np.diff(states, axis=0) * fps), axis=1), 95)) if len(states) > 1 else 0.0
    return float(np.exp(-(tracking / 0.12 + velocity / 1.5)))


def examples(segments: list[dict], episode_set: set[str], context: int, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    features, targets, future_states, confidence = [], [], [], []
    cache: dict[str, list[dict]] = {}
    for segment in segments:
        if segment["episode_id"] not in episode_set:
            continue
        path = segment["cleaned_episode"]
        rows = cache.setdefault(path, load_jsonl(Path(path)))
        start, end = segment["start_sample_index"], segment["end_sample_index"]
        if end - start + 1 < context + horizon:
            continue
        state = np.asarray([row["robot_joint_state_rad"] for row in rows], dtype=np.float32)
        command = np.asarray([row["mapped_joint_command_rad"] for row in rows], dtype=np.float32)
        for anchor in range(start + context, end - horizon + 2):
            history = np.concatenate([state[anchor - context:anchor], command[anchor - context:anchor]], axis=1)
            target = command[anchor:anchor + horizon]
            target_states = state[anchor:anchor + horizon]
            local_state = state[anchor - context:anchor + horizon]
            local_command = command[anchor - context:anchor + horizon]
            features.append(history)
            targets.append(target)
            future_states.append(target_states)
            confidence.append(quality_target(local_state, local_command, int(segment["fps"])))
    if not features:
        raise RuntimeError("no valid sequence examples")
    return (np.stack(features), np.stack(targets), np.stack(future_states), np.asarray(confidence, dtype=np.float32)[:, None])


class ConfidenceTrajectoryGRU(nn.Module):
    def __init__(self, context_features: int, hidden: int, horizon: int) -> None:
        super().__init__()
        self.horizon = horizon
        self.gru = nn.GRU(context_features, hidden, num_layers=2, batch_first=True, dropout=0.1)
        self.action_head = nn.Sequential(nn.Linear(hidden, hidden), nn.SiLU(), nn.Linear(hidden, horizon * 7))
        self.confidence_head = nn.Sequential(nn.Linear(hidden, hidden // 2), nn.SiLU(), nn.Linear(hidden // 2, 1))

    def forward(self, inputs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        encoded, _ = self.gru(inputs)
        final = encoded[:, -1]
        action = self.action_head(final).view(-1, self.horizon, 7)
        confidence = torch.sigmoid(self.confidence_head(final))
        return action, confidence


def p95(values: np.ndarray) -> float:
    return float(np.percentile(values, 95)) if len(values) else float("nan")


def evaluate(model: nn.Module, loader: DataLoader, input_mean: torch.Tensor, input_std: torch.Tensor, target_mean: torch.Tensor, target_std: torch.Tensor, fps: int) -> dict[str, float]:
    model.eval()
    predictions, targets, states = [], [], []
    with torch.no_grad():
        for inputs, target, future_state, _quality in loader:
            normalized = (inputs - input_mean) / input_std
            prediction, _confidence = model(normalized)
            predictions.append((prediction * target_std + target_mean).cpu().numpy())
            targets.append(target.cpu().numpy())
            states.append(future_state.cpu().numpy())
    prediction = np.concatenate(predictions); target = np.concatenate(targets); future_state = np.concatenate(states)
    action_mae = float(np.mean(np.abs(prediction - target)))
    tracking_rmse = float(np.sqrt(np.mean((prediction - future_state) ** 2)))
    previous = target[:, :1]
    trajectory = np.concatenate([previous, prediction], axis=1)
    velocity = np.max(np.abs(np.diff(trajectory, axis=1) * fps), axis=2).ravel()
    acceleration = np.max(np.abs(np.diff(trajectory, n=2, axis=1) * fps * fps), axis=2).ravel()
    jerk = np.max(np.abs(np.diff(trajectory, n=3, axis=1) * fps * fps * fps), axis=2).ravel()
    return {"action_mae_rad": action_mae, "tracking_rmse_rad": tracking_rmse, "velocity_p95_rad_s": p95(velocity), "acceleration_p95_rad_s2": p95(acceleration), "jerk_p95_rad_s3": p95(jerk)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--context", type=int, default=10)
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=20260826)
    args = parser.parse_args()
    torch.manual_seed(args.seed); np.random.seed(args.seed); random.seed(args.seed)
    segments = [item for item in load_jsonl(args.segments) if item.get("condition_role") == "A"]
    episode_ids = sorted({item["episode_id"] for item in segments})
    if len(episode_ids) < 10:
        raise RuntimeError("need at least 10 distinct episodes for an episode-level split")
    shuffled = episode_ids[:]; random.Random(args.seed).shuffle(shuffled)
    test_count, validation_count = max(1, round(len(shuffled) * 0.15)), max(1, round(len(shuffled) * 0.15))
    test_ids = set(shuffled[:test_count]); validation_ids = set(shuffled[test_count:test_count + validation_count]); train_ids = set(shuffled[test_count + validation_count:])
    train = examples(segments, train_ids, args.context, args.horizon)
    validation = examples(segments, validation_ids, args.context, args.horizon)
    test = examples(segments, test_ids, args.context, args.horizon)
    x_train, y_train, _state_train, q_train = [torch.from_numpy(value).float() for value in train]
    input_mean, input_std = x_train.mean(dim=(0, 1), keepdim=True), x_train.std(dim=(0, 1), keepdim=True).clamp_min(1e-6)
    target_mean, target_std = y_train.mean(dim=(0, 1), keepdim=True), y_train.std(dim=(0, 1), keepdim=True).clamp_min(1e-6)
    train_loader = DataLoader(TensorDataset(x_train, y_train, q_train), batch_size=args.batch_size, shuffle=True)
    def eval_loader(values: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]) -> DataLoader:
        return DataLoader(TensorDataset(*(torch.from_numpy(value).float() for value in values)), batch_size=args.batch_size)
    validation_loader, test_loader = eval_loader(validation), eval_loader(test)
    model = ConfidenceTrajectoryGRU(14, 64, args.horizon)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    action_loss = nn.SmoothL1Loss(); confidence_loss = nn.MSELoss()
    best_state, best_validation, remaining_patience = None, float("inf"), 12
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train(); total_loss = 0.0
        for inputs, target, confidence in train_loader:
            normalized = (inputs - input_mean) / input_std
            normalized_target = (target - target_mean) / target_std
            prediction, predicted_confidence = model(normalized)
            generated = prediction * target_std + target_mean
            velocity = torch.diff(generated, dim=1) * args.fps
            acceleration = torch.diff(velocity, dim=1) * args.fps
            jerk = torch.diff(acceleration, dim=1) * args.fps
            velocity_penalty = torch.relu(torch.abs(velocity) - 1.5).square().mean()
            acceleration_penalty = torch.relu(torch.abs(acceleration) - 8.0).square().mean()
            jerk_penalty = torch.relu(torch.abs(jerk) - 80.0).square().mean()
            loss = (action_loss(prediction, normalized_target) + 0.15 * confidence_loss(predicted_confidence, confidence)
                    + 0.01 * velocity_penalty + 0.002 * acceleration_penalty + 0.0001 * jerk_penalty)
            optimizer.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); optimizer.step()
            total_loss += float(loss.detach()) * len(inputs)
        validation_metrics = evaluate(model, validation_loader, input_mean, input_std, target_mean, target_std, args.fps)
        validation_score = validation_metrics["action_mae_rad"]
        history.append({"epoch": epoch, "train_loss": total_loss / len(x_train), "validation": validation_metrics})
        if validation_score < best_validation:
            best_validation, remaining_patience = validation_score, 12
            best_state = {name: value.detach().clone() for name, value in model.state_dict().items()}
        else:
            remaining_patience -= 1
            if remaining_patience == 0:
                break
    assert best_state is not None
    model.load_state_dict(best_state)
    metrics = evaluate(model, test_loader, input_mean, input_std, target_mean, target_std, args.fps)
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    torch.save({"model_state": model.state_dict(), "input_mean": input_mean, "input_std": input_std, "target_mean": target_mean, "target_std": target_std, "context": args.context, "horizon": args.horizon, "fps": args.fps}, output / "confidence_trajectory_gru_a_v1.pt")
    report = {"schema": "robot_teleop.confidence-trajectory-policy-report/v1", "mode": "offline_training_only", "hardware_accessed": False,
              "condition_id": "第一条件", "condition_role": "A", "model": "confidence_conditioned_gru", "sequence": {"context_frames": args.context, "horizon_frames": args.horizon, "fps": args.fps},
              "split": {"train_episode_ids": sorted(train_ids), "validation_episode_ids": sorted(validation_ids), "test_episode_ids": sorted(test_ids), "train_examples": len(train[0]), "validation_examples": len(validation[0]), "test_examples": len(test[0])},
              "best_validation_action_mae_rad": best_validation, "test_metrics": metrics,
              "loss_terms": ["smooth_l1_action", "confidence_mse", "velocity_constraint", "acceleration_constraint", "jerk_constraint"],
              "metric_notes": {"action_mae_rad": "Predicted future command versus recorded mapped command.", "tracking_rmse_rad": "Predicted future command versus recorded robot state at the same future horizon; offline only.", "velocity_p95_rad_s": "Generated command trajectory finite difference.", "acceleration_p95_rad_s2": "Generated command trajectory finite difference.", "jerk_p95_rad_s3": "Generated command trajectory finite difference."},
              "epochs_completed": len(history), "history": history}
    (output / "training_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "split.json").write_text(json.dumps(report["split"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"epochs_completed": len(history), "best_validation_action_mae_rad": best_validation, "test_metrics": metrics}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
