"""Frozen multi-camera visual encoder used by the online model worker."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np


def local_model_path(model_id: str, revision: str, cache_dir: Path) -> Path:
    repository = cache_dir / ("models--" + model_id.replace("/", "--"))
    reference = repository / "refs" / revision
    resolved = reference.read_text(encoding="utf-8").strip() if reference.is_file() else revision
    snapshot = repository / "snapshots" / resolved
    if not snapshot.is_dir():
        raise ValueError(f"model snapshot is not available: {model_id}@{revision}")
    return snapshot


class OnlineVisualEncoder:
    def __init__(self, model_id: str, revision: str, cache_dir: Path, device: str) -> None:
        import torch
        from transformers import AutoModel, AutoProcessor

        source = local_model_path(model_id, revision, cache_dir)
        self.torch = torch
        self.device = torch.device(device)
        self.processor = AutoProcessor.from_pretrained(source, use_fast=False, local_files_only=True)
        self.model = AutoModel.from_pretrained(source, local_files_only=True).to(self.device).eval()

    def encode_jpegs(self, images: list[bytes]) -> np.ndarray:
        from PIL import Image

        decoded = []
        for payload in images:
            with Image.open(BytesIO(payload)) as image:
                decoded.append(image.convert("RGB"))
        inputs = self.processor(images=decoded, return_tensors="pt")
        inputs = {name: value.to(self.device) for name, value in inputs.items()}
        with self.torch.inference_mode():
            if hasattr(self.model, "get_image_features"):
                values = self.model.get_image_features(**inputs)
            else:
                output = self.model.vision_model(**inputs)
                values = getattr(output, "pooler_output", None)
                if values is None:
                    values = output.last_hidden_state[:, 0]
            values = values / values.norm(p=2, dim=-1, keepdim=True).clamp_min(1e-12)
        return values.detach().cpu().float().numpy().reshape(-1)

