"""Configuration and path contract for the capture-to-training flywheel."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SCHEMA = "robot_teleop.flywheel-config/v1"


def resolve_path(value: str | Path, root: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


@dataclass(frozen=True)
class FlywheelConfig:
    path: Path
    repository: Path
    data_root: Path
    run_root: Path
    model_cache: Path
    processing: dict[str, Any]
    vlm: dict[str, Any]
    training: dict[str, Any]
    control: dict[str, Any]

    @property
    def quality_gate(self) -> Path:
        return resolve_path(self.processing["quality_gate"], self.repository)

    @property
    def model_config(self) -> Path:
        return resolve_path(self.training["model_config"], self.repository)

    @property
    def effective_model_config(self) -> Path:
        """Return the model config whose input contract matches this flywheel.

        A correction view has no visual tensor.  When VLM preparation is
        disabled, silently selecting the 1536-dim visual model would fail much
        later inside the trainer.  Keep the choice in configuration, with the
        repository baseline as the only fallback.
        """
        configured = self.model_config
        if self.vlm.get("enabled", True):
            return configured
        fallback = self.training.get("model_config_no_vlm", "config/filters/trajectory_cvae_transformer_v0_1.yaml")
        return resolve_path(fallback, self.repository)


def load_flywheel_config(path: Path, repository: Path) -> FlywheelConfig:
    path = path.expanduser().resolve()
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if payload.get("schema") != SCHEMA:
        raise ValueError(f"unsupported flywheel config: {payload.get('schema')}")
    storage = payload.get("storage") or {}
    processing = payload.get("processing") or {}
    vlm = payload.get("vlm") or {}
    training = payload.get("training") or {}
    control = payload.get("control") or {}
    for name in ("data_root", "run_root", "model_cache"):
        if not storage.get(name):
            raise ValueError(f"storage.{name} is required")
    for name in ("derived_name", "arm", "source_domain", "expert_action_field", "quality_gate"):
        if not processing.get(name):
            raise ValueError(f"processing.{name} is required")
    result = FlywheelConfig(
        path=path,
        repository=repository,
        data_root=resolve_path(storage["data_root"], repository),
        run_root=resolve_path(storage["run_root"], repository),
        model_cache=resolve_path(storage["model_cache"], repository),
        processing=dict(processing),
        vlm=dict(vlm),
        training=dict(training),
        control=dict(control),
    )
    model_path = result.effective_model_config
    if not model_path.is_file():
        raise ValueError(f"filter model config not found: {model_path}")
    model_payload = yaml.safe_load(model_path.read_text(encoding="utf-8")) or {}
    visual_dim = int((model_payload.get("model") or {}).get("visual_dim", -1))
    vlm_enabled = bool(result.vlm.get("enabled", True))
    expected_visual_dim = int(result.vlm.get("embedding_dim", visual_dim)) if vlm_enabled else 0
    if (vlm_enabled and visual_dim <= 0) or visual_dim != expected_visual_dim:
        mode = "enabled" if vlm_enabled else "disabled"
        requirement = "a positive embedding dimension" if vlm_enabled else "visual_dim=0"
        raise ValueError(f"VLM {mode} requires {requirement}, got visual_dim={visual_dim} in {model_path}")
    return result


def resolve_capture(source: Path) -> tuple[Path, Path]:
    """Return (capture run, rosbag) for either accepted input form."""
    source = source.expanduser().resolve()
    if (source / "metadata.yaml").is_file():
        bag = source
        run = source.parent.parent if source.parent.name == "artifacts" else source.parent
    else:
        run = source
        bag = run / "artifacts" / "rosbag2"
    if not (bag / "metadata.yaml").is_file():
        raise ValueError(f"ROS2 bag metadata not found: {bag / 'metadata.yaml'}")
    return run, bag
