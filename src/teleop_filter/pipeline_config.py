"""Versioned configuration for the correction/VLM filter-view pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


PIPELINE_CONFIG_SCHEMA = "robot_teleop.filter-training-pipeline/v0.1"


@dataclass(frozen=True)
class PipelineCamera:
    camera_id: str
    index: Path


@dataclass(frozen=True)
class FilterViewPipelineConfig:
    config_path: Path
    episode: Path
    events: Path | None
    expert_action_field: str
    output_dir: Path
    vlm_enabled: bool
    model_id: str
    revision: str
    cache_dir: Path | None
    device: str
    batch_size: int
    max_age_ms: float
    allow_network: bool
    cameras: tuple[PipelineCamera, ...]


def _reject_unknown(mapping: Mapping[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ValueError(f"unknown {name} fields: {', '.join(unknown)}")


def _bool(value: Any, *, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"pipeline config field {name} must be true or false")
    return value


def _path(value: Any, *, base: Path, name: str, required: bool = True) -> Path | None:
    if value is None or value == "":
        if required:
            raise ValueError(f"pipeline config requires {name}")
        return None
    if not isinstance(value, str):
        raise ValueError(f"pipeline config field {name} must be a path string")
    result = Path(value).expanduser()
    return result if result.is_absolute() else (base / result).resolve()


def load_pipeline_config(path: Path) -> FilterViewPipelineConfig:
    path = path.expanduser().resolve()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"pipeline config not found: {path}") from error
    if not isinstance(payload, Mapping):
        raise ValueError("pipeline config must be a mapping")
    if payload.get("schema") != PIPELINE_CONFIG_SCHEMA:
        raise ValueError(f"unsupported pipeline config schema: {payload.get('schema')}")
    _reject_unknown(payload, {"schema", "path_base", "source", "output", "vlm"}, "top-level")
    path_base = payload.get("path_base", ".")
    if not isinstance(path_base, str):
        raise ValueError("path_base must be a path string")
    base = (path.parent / path_base).resolve()
    source = payload.get("source")
    output = payload.get("output")
    vlm = payload.get("vlm") or {}
    if not isinstance(source, Mapping) or not isinstance(output, Mapping) or not isinstance(vlm, Mapping):
        raise ValueError("source, output and vlm must be mappings")
    _reject_unknown(source, {"run_directory", "projection_directory", "episode", "events", "expert_action_field"}, "source")
    _reject_unknown(output, {"directory"}, "output")
    _reject_unknown(vlm, {"enabled", "model_id", "revision", "cache_dir", "device", "batch_size", "max_age_ms", "allow_network", "cameras"}, "vlm")
    run_dir = _path(source.get("run_directory"), base=base, name="source.run_directory", required=False)
    projection_dir = _path(source.get("projection_directory"), base=base, name="source.projection_directory", required=False)
    episode = _path(source.get("episode"), base=base, name="source.episode", required=False)
    if episode is None:
        if projection_dir is None:
            raise ValueError("pipeline config requires source.episode or source.projection_directory")
        episode = projection_dir / "filter/filter_training.jsonl"
    if "events" in source:
        events = _path(source.get("events"), base=base, name="source.events", required=False)
    else:
        events = None if run_dir is None else run_dir / "artifacts/audit_events.jsonl"
    expert = source.get("expert_action_field")
    if not isinstance(expert, str) or not expert.strip():
        raise ValueError("pipeline config requires source.expert_action_field")
    output_dir = _path(output.get("directory"), base=base, name="output.directory", required=False)
    if output_dir is None:
        if projection_dir is None:
            raise ValueError("pipeline config requires output.directory or source.projection_directory")
        output_dir = projection_dir / "filter_training_vlm"
    enabled = _bool(vlm.get("enabled", True), name="vlm.enabled")
    model_id = vlm.get("model_id", "google/siglip2-base-patch16-224")
    revision = vlm.get("revision", "main")
    device = vlm.get("device", "cuda")
    if not all(isinstance(v, str) and v for v in (model_id, revision, device)):
        raise ValueError("vlm.model_id, vlm.revision and vlm.device must be non-empty strings")
    batch_value = vlm.get("batch_size", 32)
    if isinstance(batch_value, bool):
        raise ValueError("vlm.batch_size must be a positive integer")
    batch_size = int(batch_value)
    max_age_ms = float(vlm.get("max_age_ms", 100.0))
    if batch_size <= 0 or max_age_ms < 0:
        raise ValueError("vlm.batch_size must be positive and vlm.max_age_ms non-negative")
    cache_dir = _path(vlm.get("cache_dir"), base=base, name="vlm.cache_dir", required=False)
    cameras_raw = vlm.get("cameras") or []
    if not isinstance(cameras_raw, list):
        raise ValueError("vlm.cameras must be a list")
    if enabled and not cameras_raw:
        raise ValueError("vlm.cameras must contain at least one camera when VLM is enabled")
    cameras: list[PipelineCamera] = []
    seen: set[str] = set()
    for item in cameras_raw:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str) or not item.get("id"):
            raise ValueError("each vlm camera requires an id and index")
        _reject_unknown(item, {"id", "index"}, "camera")
        camera_id = item["id"]
        if camera_id in seen:
            raise ValueError(f"duplicate VLM camera id: {camera_id}")
        seen.add(camera_id)
        index = _path(item.get("index"), base=base, name=f"vlm.cameras[{camera_id}].index", required=False)
        if index is None:
            if projection_dir is None:
                raise ValueError(f"camera {camera_id} requires index without source.projection_directory")
            index = projection_dir / f"frames/{camera_id}_frames.jsonl"
        cameras.append(PipelineCamera(camera_id, index))
    return FilterViewPipelineConfig(
        config_path=path, episode=episode, events=events, expert_action_field=expert.strip(),
        output_dir=output_dir, vlm_enabled=enabled, model_id=model_id, revision=revision,
        cache_dir=cache_dir, device=device, batch_size=batch_size, max_age_ms=max_age_ms,
        allow_network=_bool(vlm.get("allow_network", False), name="vlm.allow_network"), cameras=tuple(cameras),
    )
