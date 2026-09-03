"""Small deterministic helpers for local model artifact provenance."""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_path(path: Path) -> str:
    """Hash a file or a checkpoint directory deterministically."""
    path = path.expanduser().resolve()
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    if not path.is_dir():
        raise FileNotFoundError(path)
    for item in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(b"\0")
        with item.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()
