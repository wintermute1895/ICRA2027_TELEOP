#!/usr/bin/env python3
"""Attach frozen VLM embeddings to an admitted filter-training JSONL view.

The VLM itself is intentionally external: this adapter consumes a versioned
embedding JSONL so the vision encoder can be swapped without changing the
trajectory-filter model or the capture contract.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
from pathlib import Path
from typing import Any


def stamp(row: dict[str, Any]) -> int:
    value = row.get("timestamp_ns", row.get("header_stamp_ns"))
    if not isinstance(value, int):
        raise ValueError("each row must contain integer timestamp_ns or header_stamp_ns")
    return value


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_filter_rows(source: list[dict[str, Any]]) -> None:
    required_vectors = ("master_joint_raw", "robot_joint_state_rad", "residual_target_rad")
    for index, row in enumerate(source):
        if row.get("success") is not True:
            raise ValueError(f"episode row {index} is not an admitted success row")
        for name in required_vectors:
            value = row.get(name)
            if not isinstance(value, list) or not value:
                raise ValueError(f"episode row {index} lacks non-empty {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--model-revision", default="unspecified")
    parser.add_argument("--camera-id", action="append")
    parser.add_argument("--max-age-ms", type=float, default=100.0)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite output: {args.output}")
    if args.max_age_ms < 0.0:
        raise SystemExit("--max-age-ms must be non-negative")
    source = rows(args.episode)
    camera_ids = args.camera_id or ["main_rgb"]
    if len(args.embeddings) not in {1, len(camera_ids)}:
        raise SystemExit("provide one combined --embeddings file or one file per --camera-id")
    if len(set(camera_ids)) != len(camera_ids):
        raise SystemExit("--camera-id values must be unique")
    if not source:
        raise SystemExit("episode and embedding JSONL must be non-empty")
    try:
        validate_filter_rows(source)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    tolerance_ns = int(args.max_age_ms * 1_000_000)
    output_rows = []
    missing = []
    dimensions: list[int | None] = [None] * len(camera_ids)
    embedding_streams = []
    resolved_revisions: set[str] = set()
    embedding_paths = args.embeddings * len(camera_ids) if len(args.embeddings) == 1 else args.embeddings
    for embedding_path, camera_id in zip(embedding_paths, camera_ids):
        stream = [
            row for row in rows(embedding_path)
            if row.get("camera_id", camera_id) == camera_id
        ]
        stream.sort(key=stamp)
        if not stream:
            raise SystemExit(f"no embeddings found for camera_id={camera_id}")
        for position, embedding_row in enumerate(stream):
            row_model_id = embedding_row.get("model_id")
            row_revision = embedding_row.get("model_revision")
            row_requested_revision = embedding_row.get("requested_revision")
            if row_model_id is not None and row_model_id != args.model_id:
                raise SystemExit(f"embedding row {position} for {camera_id} uses model_id={row_model_id}")
            if row_revision is not None:
                resolved_revisions.add(str(row_revision))
            if (
                row_revision is not None
                and args.model_revision != "unspecified"
                and args.model_revision not in {row_revision, row_requested_revision}
            ):
                raise SystemExit(f"embedding row {position} for {camera_id} uses model_revision={row_revision}")
        embedding_streams.append((stream, [stamp(row) for row in stream]))
    if len(resolved_revisions) > 1:
        raise SystemExit(f"embedding inputs contain multiple resolved model revisions: {sorted(resolved_revisions)}")
    resolved_revision = next(iter(resolved_revisions), args.model_revision)
    for index, row in enumerate(source):
        timestamp = stamp(row)
        selected_embeddings = []
        selected_meta = []
        row_missing = []
        for camera_id, (stream, stamps) in zip(camera_ids, embedding_streams):
            position = bisect.bisect_right(stamps, timestamp) - 1
            selected = stream[position] if position >= 0 else None
            if selected is None or timestamp - stamp(selected) > tolerance_ns:
                row_missing.append(camera_id)
                continue
            embedding = selected.get("embedding", selected.get("vlm_embedding"))
            if not isinstance(embedding, list) or not embedding:
                raise SystemExit(f"embedding row {position} for {camera_id} has no non-empty list")
            camera_index = camera_ids.index(camera_id)
            if dimensions[camera_index] is None:
                dimensions[camera_index] = len(embedding)
            if len(embedding) != dimensions[camera_index] or not all(isinstance(value, (int, float)) for value in embedding):
                raise SystemExit(f"inconsistent embedding dimension or non-numeric value for {camera_id}")
            selected_embeddings.extend(float(value) for value in embedding)
            selected_meta.append({
                "camera_id": camera_id,
                "source_timestamp_ns": stamp(selected),
                "age_ms": (timestamp - stamp(selected)) / 1_000_000.0,
            })
        if row_missing:
            missing.append({"index": index, "timestamp_ns": timestamp, "camera_ids": row_missing})
            continue
        enriched = dict(row)
        enriched["vlm_embedding"] = selected_embeddings
        enriched["vlm"] = {
            "model_id": args.model_id,
            "model_revision": resolved_revision,
            "camera_ids": camera_ids,
            "camera_embeddings": selected_meta,
        }
        output_rows.append(enriched)
    if missing:
        raise SystemExit(
            f"{len(missing)} episode rows lack an aligned embedding for camera(s) "
            f"{camera_ids}; "
            "refusing partial visual training view"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    manifest = {
        "schema": "robot_teleop.vlm-embedding-attachment/v0.1",
        "source_episode": str(args.episode.resolve()),
        "source_episode_sha256": hashlib.sha256(args.episode.read_bytes()).hexdigest(),
        "source_embeddings": [str(path.resolve()) for path in args.embeddings],
        "source_embeddings_sha256": [hashlib.sha256(path.read_bytes()).hexdigest() for path in args.embeddings],
        "model_id": args.model_id,
        "requested_model_revision": args.model_revision,
        "model_revision": resolved_revision,
        "camera_ids": camera_ids,
        "embedding_dims": dimensions,
        "embedding_dim": sum(dimensions),
        "alignment": {"policy": "latest_not_after", "max_age_ms": args.max_age_ms},
        "rows": len(output_rows),
    }
    args.output.with_suffix(args.output.suffix + ".manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), "rows": len(output_rows), "embedding_dim": sum(dimensions)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
