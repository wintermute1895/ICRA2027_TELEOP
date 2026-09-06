"""Lightweight task configuration and template APIs."""

from .task_config import load_task_bundle, load_task_registry, resolve_registered_task, task_capture_value
from .task_templates import ConfigTask, TaskTemplate, create_task
from .deployment import ActionSupervisor, DeploymentDecision, DeploymentLimits, DeploymentMode

__all__ = ["ConfigTask", "TaskTemplate", "create_task", "load_task_bundle", "load_task_registry", "resolve_registered_task", "task_capture_value", "ActionSupervisor", "DeploymentDecision", "DeploymentLimits", "DeploymentMode"]
