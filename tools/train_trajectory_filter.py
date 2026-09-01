#!/usr/bin/env python3
"""Train the task-aware residual CVAE from admitted filter-training JSONL."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader, TensorDataset
from torch.nn import functional as F


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from teleop_filter import ConditionalTrajectoryVAE, TrajectoryFilterConfig, trajectory_vae_loss  # noqa: E402


@dataclass
class EpisodeWindows:
    commands: np.ndarray
    states: np.ndarray
    contexts: np.ndarray | None
    visuals: np.ndarray | None
    targets: np.ndarray
    correction_mask: np.ndarray
    correction_weights: np.ndarray
    target_semantics: str
    episode_id: str
    visual_provenance: dict[str, object] | None = None


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def vector(row: dict, name: str, size: int) -> np.ndarray | None:
    value = row.get(name)
    if not isinstance(value, list) or len(value) != size:
        return None
    result = np.asarray(value, dtype=np.float32)
    return result if np.isfinite(result).all() else None


def correction_flags(rows: list[dict]) -> np.ndarray:
    """Materialize timestamped auditor events into a per-row correction mask."""
    flags = []
    active = False
    for index, row in enumerate(rows):
        if isinstance(row.get("correction_mask"), (bool, int, float)):
            active = bool(row["correction_mask"])
        elif isinstance(row.get("correction_active"), bool):
            active = row["correction_active"]
        elif isinstance(row.get("correction_interval"), list) and len(row["correction_interval"]) == 2:
            start, end = row["correction_interval"]
            active = int(start) <= index <= int(end)
        else:
            if row.get("correction_start") is True:
                active = True
            if row.get("correction_end") is True:
                active = False
        flags.append(active)
    return np.asarray(flags, dtype=np.float32)


def build_windows(
    path: Path,
    *,
    history_length: int,
    horizon: int,
    context_dim: int,
    visual_dim: int = 0,
    action_dim: int | None = None,
    state_dim: int | None = None,
    correction_loss_weight: float = 1.0,
    allow_synthetic_smoke: bool = False,
) -> EpisodeWindows:
    rows = read_jsonl(path)
    if not rows:
        raise ValueError(f"empty episode: {path}")
    if any(row.get("success") is not True for row in rows):
        raise ValueError(f"episode is not an admitted success view: {path}")
    if correction_loss_weight < 0.0:
        raise ValueError("correction_loss_weight must be non-negative")
    target_name = "expert_action_target_rad"
    if not any(target_name in row for row in rows):
        # Kept solely for isolated historical smoke fixtures. It is never
        # accepted unless the fixture explicitly identifies its synthetic source.
        target_name = "residual_target_rad"
        synthetic = {row.get("action_target_source", row.get("correction_label_source")) for row in rows}
        if not allow_synthetic_smoke or synthetic != {"synthetic_smoke_only"}:
            raise ValueError(
                "episode lacks expert_action_target_rad; "
                "build a correction-segment view with recorded_expert_action targets"
            )
    inferred_action = len(rows[0].get(target_name) or [])
    inferred_state = len(rows[0].get("robot_joint_state_rad") or [])
    action_dim = action_dim or inferred_action
    state_dim = state_dim or inferred_state
    if action_dim < 1 or state_dim < 1:
        raise ValueError(f"cannot infer action/state dimensions: {path}")
    visual_provenance = None
    if visual_dim:
        provenance = set()
        for row in rows:
            vlm = row.get("vlm")
            if not isinstance(vlm, dict):
                raise ValueError(f"episode lacks VLM provenance: {path}")
            provenance.add((vlm.get("model_id"), vlm.get("model_revision"), tuple(vlm.get("camera_ids") or ())))
        if len(provenance) != 1:
            raise ValueError(f"episode contains inconsistent VLM provenance: {path}")
        model_id, model_revision, camera_ids = next(iter(provenance))
        if not isinstance(model_id, str) or not isinstance(model_revision, str) or not camera_ids:
            raise ValueError(f"episode lacks complete VLM model/camera provenance: {path}")
        visual_provenance = {
            "model_id": model_id,
            "model_revision": model_revision,
            "camera_ids": list(camera_ids),
            "embedding_dim": visual_dim,
        }

    command_windows, state_windows, context_windows, visual_windows, targets, masks, weights = [], [], [], [], [], [], []
    flags = correction_flags(rows)
    for anchor in range(history_length, len(rows) - horizon + 1):
        history_rows = rows[anchor - history_length:anchor]
        future_rows = rows[anchor:anchor + horizon]
        commands = [vector(row, "master_joint_raw", action_dim) for row in history_rows]
        states = [vector(row, "robot_joint_state_rad", state_dim) for row in history_rows]
        if int(horizon) != 1:
            raise ValueError("the task-aware residual MVP requires horizon=1")
        future = [vector(row, target_name, action_dim) for row in future_rows]
        if any(value is None for value in (*commands, *states, *future)):
            continue
        contexts = None
        if context_dim:
            contexts = [vector(row, "filter_context", context_dim) for row in history_rows]
            if any(value is None for value in contexts):
                continue
        visuals = None
        if visual_dim:
            visuals = [vector(row, "vlm_embedding", visual_dim) for row in history_rows]
            if any(value is None for value in visuals):
                continue
        command_windows.append(np.stack(commands))
        state_windows.append(np.stack(states))
        targets.append(np.stack(future))
        mask = flags[anchor:anchor + horizon]
        masks.append(mask)
        weights.append((1.0 + correction_loss_weight * mask)[..., None])
        if contexts is not None:
            context_windows.append(np.stack(contexts))
        if visuals is not None:
            visual_windows.append(np.stack(visuals))
    if not targets:
        raise ValueError(
            f"no complete expert-action windows in episode: {path}; "
            "provide expert_action_target_rad from a verified correction segment"
        )
    episode_id = str(rows[0].get("episode_id") or path.stem)
    return EpisodeWindows(
        commands=np.stack(command_windows),
        states=np.stack(state_windows),
        contexts=np.stack(context_windows) if context_dim else None,
        visuals=np.stack(visual_windows) if visual_dim else None,
        targets=np.stack(targets),
        correction_mask=np.stack(masks),
        correction_weights=np.stack(weights),
        target_semantics="recorded_expert_action" if target_name == "expert_action_target_rad" else "synthetic_smoke_residual",
        episode_id=episode_id,
        visual_provenance=visual_provenance,
    )


def stack(items: list[EpisodeWindows]) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None, np.ndarray, np.ndarray, np.ndarray]:
    if not items:
        raise ValueError("at least one episode is required")
    context_presence = {item.contexts is not None for item in items}
    visual_presence = {item.visuals is not None for item in items}
    if len(context_presence) != 1 or len(visual_presence) != 1:
        raise ValueError("all episodes must use the same context and visual feature contract")
    if items[0].contexts is not None and any(item.contexts.shape[-1] != items[0].contexts.shape[-1] for item in items):
        raise ValueError("all episodes must use the same context dimension")
    if items[0].visuals is not None and any(item.visuals.shape[-1] != items[0].visuals.shape[-1] for item in items):
        raise ValueError("all episodes must use the same visual embedding dimension")
    if any(item.visual_provenance != items[0].visual_provenance for item in items):
        raise ValueError("all episodes must use identical VLM model revision and camera order")
    if any(item.target_semantics != items[0].target_semantics for item in items):
        raise ValueError("all episodes must use identical action-target semantics")
    commands = np.concatenate([item.commands for item in items])
    states = np.concatenate([item.states for item in items])
    targets = np.concatenate([item.targets for item in items])
    correction_mask = np.concatenate([item.correction_mask for item in items])
    correction_weights = np.concatenate([item.correction_weights for item in items])
    contexts = None if items[0].contexts is None else np.concatenate([item.contexts for item in items])
    visuals = None if items[0].visuals is None else np.concatenate([item.visuals for item in items])
    return commands, states, contexts, visuals, targets, correction_mask, correction_weights


def mean_std(array: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    axes = tuple(range(array.ndim - 1))
    mean = array.mean(axis=axes, keepdims=True).astype(np.float32)
    std = array.std(axis=axes, keepdims=True).clip(1e-6).astype(np.float32)
    return mean, std


def loader(
    arrays: tuple[np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None, np.ndarray, np.ndarray, np.ndarray],
    normalization: dict[str, tuple[np.ndarray, np.ndarray]],
    batch_size: int,
    shuffle: bool,
) -> DataLoader:
    commands, states, contexts, visuals, targets, correction_mask, correction_weights = arrays
    commands = (commands - normalization["commands"][0]) / normalization["commands"][1]
    states = (states - normalization["states"][0]) / normalization["states"][1]
    targets = (targets - normalization["targets"][0]) / normalization["targets"][1]
    tensors = [torch.from_numpy(commands), torch.from_numpy(states)]
    if contexts is not None:
        contexts = (contexts - normalization["contexts"][0]) / normalization["contexts"][1]
        tensors.append(torch.from_numpy(contexts))
    if visuals is not None:
        visuals = (visuals - normalization["visuals"][0]) / normalization["visuals"][1]
        tensors.append(torch.from_numpy(visuals))
    tensors.append(torch.from_numpy(targets))
    tensors.append(torch.from_numpy(correction_mask))
    tensors.append(torch.from_numpy(correction_weights))
    return DataLoader(TensorDataset(*tensors), batch_size=batch_size, shuffle=shuffle)


def run_epoch(
    model: ConditionalTrajectoryVAE,
    batches: DataLoader,
    optimizer: torch.optim.Optimizer | None,
    *,
    context_dim: int,
    visual_dim: int,
    beta_kl: float,
    smoothness_weight: float,
    device: torch.device,
) -> dict[str, float]:
    model.train(optimizer is not None)
    totals = {key: 0.0 for key in ("total", "reconstruction", "kl", "smoothness", "correction_reconstruction", "background_reconstruction")}
    metric_counts = {"correction_reconstruction": 0, "background_reconstruction": 0}
    samples = 0
    with torch.set_grad_enabled(optimizer is not None):
        for batch in batches:
            commands, states = batch[0].to(device), batch[1].to(device)
            offset = 2
            context = batch[offset].to(device) if context_dim else None
            offset += int(bool(context_dim))
            visual = batch[offset].to(device) if visual_dim else None
            offset += int(bool(visual_dim))
            targets = batch[offset].to(device)
            correction_mask = batch[offset + 1].to(device)
            correction_weights = batch[offset + 2].to(device)
            outputs = model(commands, states, targets, context, visual)
            losses = trajectory_vae_loss(
                outputs, targets, beta_kl=beta_kl, smoothness_weight=smoothness_weight,
                reconstruction_weights=correction_weights,
            )
            if optimizer is not None:
                optimizer.zero_grad()
                losses["total"].backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            count = len(commands)
            samples += count
            for key in totals:
                totals[key] += float(losses[key].detach()) * count
            element_loss = F.smooth_l1_loss(outputs["prediction"], targets, reduction="none").mean(dim=-1)
            for name, selected in (("correction_reconstruction", correction_mask > 0.5), ("background_reconstruction", correction_mask <= 0.5)):
                if selected.any():
                    selected_count = int(selected.sum())
                    totals[name] += float(element_loss[selected].sum().detach())
                    metric_counts[name] += selected_count
    metrics = {key: value / samples for key, value in totals.items() if key not in metric_counts}
    metrics.update({key: (totals[key] / metric_counts[key] if metric_counts[key] else 0.0) for key in metric_counts})
    return metrics | {"samples": samples, "correction_windows": metric_counts["correction_reconstruction"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, action="append", required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "config/filters/trajectory_cvae_transformer_v0_1.yaml")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260831)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite output: {args.output_dir}")
    if args.epochs < 1 or args.batch_size < 1 or not 0.0 <= args.validation_fraction < 1.0:
        raise SystemExit("invalid epochs, batch size, or validation fraction")

    payload = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if payload.get("schema") != "robot_teleop.trajectory-filter-model/v0.1":
        raise SystemExit("unsupported model config schema")
    model_values = payload["model"]
    first = build_windows(
        args.episode[0], history_length=int(model_values["history_length"]),
        horizon=int(model_values["horizon"]), context_dim=int(model_values["context_dim"]),
        visual_dim=int(model_values.get("visual_dim", 0)),
        correction_loss_weight=float(payload["loss"].get("correction_weight", 1.0)),
        allow_synthetic_smoke=bool(payload.get("data", {}).get("allow_synthetic_smoke", False)),
    )
    action_dim, state_dim = first.commands.shape[-1], first.states.shape[-1]
    episodes = [first]
    for path in args.episode[1:]:
        episodes.append(build_windows(
            path, history_length=int(model_values["history_length"]),
            horizon=int(model_values["horizon"]), context_dim=int(model_values["context_dim"]),
            visual_dim=int(model_values.get("visual_dim", 0)),
            action_dim=action_dim, state_dim=state_dim,
            correction_loss_weight=float(payload["loss"].get("correction_weight", 1.0)),
            allow_synthetic_smoke=bool(payload.get("data", {}).get("allow_synthetic_smoke", False)),
        ))
    if len({item.episode_id for item in episodes}) != len(episodes):
        raise SystemExit("duplicate episode_id in inputs")

    random.Random(args.seed).shuffle(episodes)
    validation_count = max(1, round(len(episodes) * args.validation_fraction)) if len(episodes) > 1 and args.validation_fraction else 0
    validation_episodes = episodes[:validation_count]
    train_episodes = episodes[validation_count:]
    train_arrays = stack(train_episodes)
    normalization = {
        "commands": mean_std(train_arrays[0]), "states": mean_std(train_arrays[1]),
        "targets": mean_std(train_arrays[4]),
    }
    if train_arrays[2] is not None:
        normalization["contexts"] = mean_std(train_arrays[2])
    if train_arrays[3] is not None:
        normalization["visuals"] = mean_std(train_arrays[3])

    config = TrajectoryFilterConfig(
        action_dim=action_dim, state_dim=state_dim,
        history_length=int(model_values["history_length"]), horizon=int(model_values["horizon"]),
        context_dim=int(model_values["context_dim"]), visual_dim=int(model_values.get("visual_dim", 0)),
        latent_dim=int(model_values["latent_dim"]),
        model_dim=int(model_values["model_dim"]), num_heads=int(model_values["num_heads"]),
        num_layers=int(model_values["num_layers"]), dropout=float(model_values["dropout"]),
    )
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device(args.device)
    model = ConditionalTrajectoryVAE(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    train_loader = loader(train_arrays, normalization, args.batch_size, True)
    validation_loader = loader(stack(validation_episodes), normalization, args.batch_size, False) if validation_episodes else None
    loss_cfg = payload["loss"]
    history = []
    for epoch in range(1, args.epochs + 1):
        train_metrics = run_epoch(
            model, train_loader, optimizer, context_dim=config.context_dim, visual_dim=config.visual_dim,
            beta_kl=float(loss_cfg["beta_kl"]), smoothness_weight=float(loss_cfg["smoothness_weight"]),
            device=device,
        )
        validation_metrics = None if validation_loader is None else run_epoch(
            model, validation_loader, None, context_dim=config.context_dim, visual_dim=config.visual_dim,
            beta_kl=float(loss_cfg["beta_kl"]), smoothness_weight=float(loss_cfg["smoothness_weight"]),
            device=device,
        )
        history.append({"epoch": epoch, "train": train_metrics, "validation": validation_metrics})
        print(json.dumps(history[-1]))

    args.output_dir.mkdir(parents=True)
    checkpoint = {
        "schema": "robot_teleop.trajectory-filter-checkpoint/v0.1",
        "model_config": config.to_dict(),
        "model_state": model.cpu().state_dict(),
        "normalization": {key: {"mean": mean, "std": std} for key, (mean, std) in normalization.items()},
        "visual_encoder": train_episodes[0].visual_provenance,
        "target_semantics": train_episodes[0].target_semantics,
        "runtime": payload["runtime"],
    }
    torch.save(checkpoint, args.output_dir / "trajectory_filter.pt")
    sources = [{
        "path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
    } for path in args.episode]
    report = {
        "schema": "robot_teleop.trajectory-filter-training-report/v0.1",
        "model": config.to_dict(), "config": str(args.config.resolve()), "sources": sources,
        "split": {
            "train_episode_ids": [item.episode_id for item in train_episodes],
            "validation_episode_ids": [item.episode_id for item in validation_episodes],
        },
        "device": str(device), "seed": args.seed, "history": history,
        "visual_encoder": train_episodes[0].visual_provenance,
        "target_semantics": train_episodes[0].target_semantics,
        "correction_weight": float(loss_cfg.get("correction_weight", 1.0)),
        "deployment": "offline_and_simulation_only",
    }
    (args.output_dir / "training_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checkpoint": str(args.output_dir / "trajectory_filter.pt"), "epochs": args.epochs}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
