#!/usr/bin/env python3
"""Generate versioned frozen image embeddings with a CLIP/SigLIP VLM.

This is an offline preprocessing tool. It never imports ROS and never publishes
commands. The output is consumed by attach_vlm_embeddings.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_frame_rows(frame_paths: list[Path], camera_ids: list[str]) -> list[tuple[Path, dict[str, Any]]]:
    if len(frame_paths) != len(camera_ids):
        raise ValueError("--frames count must match --camera-id count")
    if len(set(camera_ids)) != len(camera_ids):
        raise ValueError("--camera-id values must be unique")
    selected: list[tuple[Path, dict[str, Any]]] = []
    for frame_path, camera_id in zip(frame_paths, camera_ids):
        rows = [
            json.loads(line)
            for line in frame_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        camera_rows = [row for row in rows if row.get("camera_id", camera_id) == camera_id]
        if not camera_rows:
            raise ValueError(f"no frames found for camera_id={camera_id} in {frame_path}")
        selected.extend((frame_path, row | {"camera_id": camera_id}) for row in camera_rows)
    return selected


def frame_reference(index_path: Path, row: dict[str, Any]) -> Path:
    value = row.get("reference", {}).get("frame_reference")
    if not isinstance(value, str):
        raise ValueError("frame row has no string reference.frame_reference")
    path = Path(value)
    return path if path.is_absolute() else index_path.parent / path


def resolve_local_model(model_id: str, revision: str, cache_dir: Path | None) -> tuple[str, str]:
    direct = Path(model_id)
    if direct.is_dir():
        return str(direct), revision
    if cache_dir is None:
        return model_id, revision
    repository = cache_dir / ("models--" + model_id.replace("/", "--"))
    resolved_revision = revision
    reference = repository / "refs" / revision
    if reference.is_file():
        resolved_revision = reference.read_text(encoding="utf-8").strip()
    snapshot = repository / "snapshots" / resolved_revision
    if not snapshot.is_dir():
        raise ValueError(
            f"model {model_id}@{revision} is not present under cache {cache_dir}; "
            "run scripts/install_vlm.sh --download first"
        )
    return str(snapshot), resolved_revision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, action="append", required=True, help="repeatable extract_rosbag_images.py JSONL")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-id", default="google/siglip2-base-patch16-224")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--cache-dir", type=Path, help="explicit local Hugging Face cache")
    parser.add_argument("--camera-id", action="append", help="repeat in the same order as --frames")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--local-files-only", action="store_true", help="refuse network access and use the local cache")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite output: {args.output}")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    camera_ids = args.camera_id or (["main_rgb"] if len(args.frames) == 1 else [])
    if not camera_ids:
        raise SystemExit("multi-camera encoding requires one --camera-id per --frames input")
    try:
        import torch
        from PIL import Image
        from transformers import AutoModel, AutoProcessor
    except ImportError as error:
        raise SystemExit(
            "VLM dependencies are missing; install requirements-vlm.txt in the training environment"
        ) from error

    try:
        frame_rows = load_frame_rows(args.frames, camera_ids)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    device = torch.device(args.device)
    load_source = args.model_id
    cache_revision = args.revision
    if args.local_files_only:
        try:
            load_source, cache_revision = resolve_local_model(args.model_id, args.revision, args.cache_dir)
        except ValueError as error:
            raise SystemExit(str(error)) from error
    load_options = {"revision": args.revision, "local_files_only": args.local_files_only, "cache_dir": args.cache_dir}
    if load_source != args.model_id:
        load_options.pop("revision")
        load_options.pop("cache_dir")
    processor = AutoProcessor.from_pretrained(load_source, use_fast=False, **load_options)
    model = AutoModel.from_pretrained(load_source, **load_options).to(device).eval()
    resolved_revision = getattr(model.config, "_commit_hash", None) or cache_revision
    output_rows = []
    with torch.inference_mode():
        for offset in range(0, len(frame_rows), args.batch_size):
            batch = frame_rows[offset:offset + args.batch_size]
            images = []
            for index_path, row in batch:
                reference = frame_reference(index_path, row)
                if not reference.is_file():
                    raise SystemExit(f"frame has no readable frame_reference: {reference}")
                with Image.open(reference) as image:
                    images.append(image.convert("RGB"))
            inputs = processor(images=images, return_tensors="pt")
            inputs = {key: value.to(device) for key, value in inputs.items()}
            if hasattr(model, "get_image_features"):
                embeddings = model.get_image_features(**inputs)
            else:
                outputs = model.vision_model(**inputs)
                pooled = getattr(outputs, "pooler_output", None)
                if pooled is None:
                    pooled = outputs.last_hidden_state[:, 0]
                embeddings = pooled
            embeddings = embeddings / embeddings.norm(p=2, dim=-1, keepdim=True).clamp_min(1e-12)
            for (_, row), embedding in zip(batch, embeddings):
                output_rows.append({
                    "schema": "robot_teleop.vlm-embedding/v0.1",
                    "timestamp_ns": int(row["timestamp_ns"]),
                    "camera_id": row["camera_id"],
                    "model_id": args.model_id,
                    "requested_revision": args.revision,
                    "model_revision": resolved_revision,
                    "embedding": embedding.cpu().float().tolist(),
                })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    manifest = {
        "schema": "robot_teleop.vlm-embedding-manifest/v0.1",
        "model_family": "frozen_vision_language_image_encoder",
        "model_id": args.model_id,
        "requested_revision": args.revision,
        "model_revision": resolved_revision,
        "camera_ids": camera_ids,
        "frames_inputs": [str(path.resolve()) for path in args.frames],
        "frames_inputs_sha256": [hashlib.sha256(path.read_bytes()).hexdigest() for path in args.frames],
        "embedding_dim": len(output_rows[0]["embedding"]),
        "rows": len(output_rows),
        "normalization": "l2",
        "processor": {"use_fast": False},
        "device": str(device),
        "batch_size": args.batch_size,
        "local_files_only": args.local_files_only,
    }
    args.output.with_suffix(args.output.suffix + ".manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), "rows": len(output_rows), "embedding_dim": manifest["embedding_dim"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
