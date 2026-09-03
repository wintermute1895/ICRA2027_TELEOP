"""Template classes for task-specific behavior without task-name branches."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar


class TaskTemplate(ABC):
    """Base contract shared by all task implementations."""

    template_key: ClassVar[str]

    def __init__(self, bundle: dict[str, Any]):
        self.bundle = bundle

    @property
    def task_id(self) -> str:
        return str(self.bundle["task_id"])

    @property
    def revision(self) -> str:
        return str(self.bundle["task_revision"])

    @property
    def phases(self) -> tuple[str, ...]:
        return tuple(self.bundle.get("phase_order", ()))

    @abstractmethod
    def validate_episode(self, episode: dict[str, Any]) -> list[str]:
        """Return contract violations; an empty list means structurally valid."""


class ConfigTask(TaskTemplate):
    """Default template for data-driven tasks.

    Task-specific semantics stay in YAML contracts. A future implementation can
    subclass this template and advertise a new ``template_key`` without adding
    task-name conditionals to the registry.
    """

    template_key = "config"

    def validate_episode(self, episode: dict[str, Any]) -> list[str]:
        required = self.bundle.get("recording_contract", {}).get("required_signals", ())
        return [f"missing required signal: {name}" for name in required if name not in episode]


_TEMPLATES: dict[str, type[TaskTemplate]] = {ConfigTask.template_key: ConfigTask}


def register_template(template: type[TaskTemplate]) -> type[TaskTemplate]:
    key = getattr(template, "template_key", "")
    if not key:
        raise ValueError("task template requires template_key")
    _TEMPLATES[key] = template
    return template


def create_task(bundle: dict[str, Any]) -> TaskTemplate:
    key = bundle.get("template", bundle.get("task_template", ConfigTask.template_key))
    try:
        template = _TEMPLATES[str(key)]
    except KeyError as exc:
        raise ValueError(f"unknown task template: {key}") from exc
    return template(bundle)
