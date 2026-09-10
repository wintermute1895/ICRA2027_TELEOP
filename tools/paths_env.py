"""Expand ${VAR} placeholders (e.g. ${TELEOP_DATA_ROOT}) in runtime config paths.

Runtime YAMLs may pin model/data paths on removable disks whose mount points
change between sessions.  The stable contract is the layout below the disk
root; scripts/resolve_data_disk.sh discovers the root at launch time and the
deployment entrypoints export it as TELEOP_DATA_ROOT.
"""
from __future__ import annotations

import os
from typing import Any

PATH_KEYS = ("checkpoint", "dataset_stats", "model_cache")


def expand_config_paths(config: dict[str, Any]) -> dict[str, Any]:
    expanded = dict(config)
    for key in PATH_KEYS:
        value = expanded.get(key)
        if isinstance(value, str) and value:
            expanded[key] = os.path.expandvars(value)
    return expanded
