"""Loading and validation for versioned task bundles."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
TASK_SCHEMA = "robot_teleop.task-bundle/v1"
LEGACY_SCHEMA = "robot_teleop.task-profile/v1"
_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _path(value: str | Path, base: Path = ROOT) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    root_candidate = (ROOT / candidate).resolve()
    if root_candidate.exists() or base == ROOT:
        return root_candidate
    return (base / candidate).resolve()


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_task_bundle(path: str | Path) -> tuple[dict[str, Any], dict[str, str]]:
    requested = _path(path)
    if requested.is_dir():
        requested = requested / "task.yaml"
    if not requested.is_file():
        raise ValueError(f"task profile not found: {requested}")

    def read(current: Path, ancestry: tuple[Path, ...]) -> tuple[dict[str, Any], dict[str, str]]:
        current = current.resolve()
        if current in ancestry:
            chain = " -> ".join(str(item) for item in (*ancestry, current))
            raise ValueError(f"cyclic task inheritance: {chain}")
        data = yaml.safe_load(current.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"task profile must be a mapping: {current}")
        if data.get("schema") not in (TASK_SCHEMA, LEGACY_SCHEMA):
            raise ValueError(f"unsupported task schema in {current}: {data.get('schema')!r}")
        hashes = {str(current.relative_to(ROOT)): hashlib.sha256(current.read_bytes()).hexdigest()}
        parent = data.get("extends")
        if not parent:
            return data, hashes
        parent_data, parent_hashes = read(_path(parent, current.parent), (*ancestry, current))
        merged = _merge(parent_data, data)
        if "task_family" not in data and isinstance(parent_data.get("task_id"), str):
            # Use the immediate parent's task id as the family for legacy
            # profiles; do not inherit a grandparent's already-derived label.
            merged["task_family"] = parent_data["task_id"]
        return merged, parent_hashes | hashes

    resolved, hashes = read(requested, ())
    task_id = resolved.get("task_id")
    revision = resolved.get("task_revision")
    if not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id):
        raise ValueError("task bundle requires a valid task_id")
    if not isinstance(revision, str) or not revision:
        raise ValueError(f"task bundle {task_id} requires task_revision")
    resolved["task_bundle_path"] = str(requested.relative_to(ROOT))
    resolved["task_bundle_sha256"] = hashlib.sha256(
        "".join(f"{key}:{hashes[key]}\n" for key in sorted(hashes)).encode("utf-8")
    ).hexdigest()
    resolved["profile_sha256"] = hashes
    return resolved, hashes


def task_capture_value(bundle: dict[str, Any], key: str, default: Any = None) -> Any:
    capture = bundle.get("capture_contract", {})
    if not isinstance(capture, dict):
        raise ValueError("capture_contract must be a mapping")
    return capture.get(key, default)


def load_task_registry(path: str | Path = "config/tasks/registry.yaml") -> dict[str, str]:
    """Return the configured task-id to bundle-path mapping."""
    registry_path = _path(path)
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "robot_teleop.task-registry/v1":
        raise ValueError(f"unsupported task registry: {registry_path}")
    entries = data.get("tasks")
    if not isinstance(entries, list):
        raise ValueError("task registry requires a tasks list")
    result: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("task_id"), str) or not isinstance(entry.get("profile"), str):
            raise ValueError("each registry task requires task_id and profile")
        task_id = entry["task_id"]
        if task_id in result:
            raise ValueError(f"duplicate task_id in registry: {task_id}")
        result[task_id] = entry["profile"]
    return result


def resolve_registered_task(task_id: str, registry: str | Path = "config/tasks/registry.yaml") -> tuple[dict[str, Any], dict[str, str]]:
    entries = load_task_registry(registry)
    if task_id not in entries:
        raise ValueError(f"task is not registered: {task_id}")
    bundle, hashes = load_task_bundle(entries[task_id])
    if bundle["task_id"] != task_id:
        raise ValueError(f"registry task_id {task_id} disagrees with bundle {bundle['task_id']}")
    return bundle, hashes
