#!/usr/bin/env python3
"""Run a frozen Qwen2.5-VL auditor on timestamped RGB keyframes.

The output is a weak, confidence-bearing audit view. It is never treated as
ground truth and never publishes robot commands.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_PROMPT = """You are an offline visual auditor for a robot precision-alignment demonstration.
The image is a timestamped contact sheet. It may contain one or two camera views.
Return exactly one JSON object and no markdown with these fields:
phase: one of approach, align, short_insert, retreat, terminal, unknown
target_visible: boolean or null
progress_consistent: boolean or null
stall: boolean or null
misaligned: boolean or null
recovery: boolean or null
success_visual: boolean or null
confidence: number from 0 to 1
notes: short evidence-based string
Use null when the image does not support a judgment. Do not infer force, contact,
operator intent, or hidden state from the image."""


def parse_json(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def nearest(rows: list[dict[str, Any]], timestamp_ns: int, tolerance_ns: int) -> dict[str, Any] | None:
    if not rows:
        return None
    selected = min(rows, key=lambda row: abs(int(row["timestamp_ns"]) - timestamp_ns))
    return selected if abs(int(selected["timestamp_ns"]) - timestamp_ns) <= tolerance_ns else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keyframes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-samples", type=int, default=8)
    parser.add_argument("--max-camera-age-ms", type=float, default=250.0)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite output: {args.output}")
    rows = [json.loads(line) for line in args.keyframes.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise SystemExit("keyframe index is empty")
    try:
        import torch
        from PIL import Image, ImageDraw
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
    except ImportError as error:
        raise SystemExit("install requirements-vlm.txt and use the teleop-train environment") from error
    if not args.model.is_dir():
        raise SystemExit(f"local Qwen model directory does not exist: {args.model}")
    cameras = sorted({str(row["camera_id"]) for row in rows})
    by_camera = {camera: sorted((row for row in rows if row["camera_id"] == camera), key=lambda row: int(row["timestamp_ns"])) for camera in cameras}
    anchors = sorted({int(row["timestamp_ns"]) for row in rows})
    if len(anchors) > args.max_samples:
        positions = [round(i * (len(anchors) - 1) / (args.max_samples - 1)) for i in range(args.max_samples)] if args.max_samples > 1 else [0]
        anchors = [anchors[position] for position in positions]
    processor = AutoProcessor.from_pretrained(str(args.model), local_files_only=True, use_fast=False)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        str(args.model), local_files_only=True, torch_dtype="auto", device_map="auto" if args.device == "auto" else None
    )
    if args.device != "auto":
        model = model.to(torch.device(args.device))
    model.eval()
    output_rows = []
    tolerance_ns = int(args.max_camera_age_ms * 1_000_000)
    for anchor in anchors:
        selected = [(camera, nearest(by_camera[camera], anchor, tolerance_ns)) for camera in cameras]
        selected = [(camera, row) for camera, row in selected if row is not None]
        if not selected:
            continue
        images = []
        for camera, row in selected:
            with Image.open(row["reference"]) as image:
                image = image.convert("RGB")
                draw = ImageDraw.Draw(image)
                draw.rectangle((0, 0, 220, 28), fill=(0, 0, 0))
                draw.text((6, 6), f"{camera} {int(row['timestamp_ns'])}", fill=(255, 255, 255))
                images.append(image)
        width = sum(image.width for image in images)
        height = max(image.height for image in images)
        contact = Image.new("RGB", (width, height), "black")
        offset = 0
        for image in images:
            contact.paste(image, (offset, 0))
            offset += image.width
        messages = [{"role": "user", "content": [{"type": "image", "image": contact}, {"type": "text", "text": SCHEMA_PROMPT}]}]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[contact], padding=True, return_tensors="pt")
        target_device = next(model.parameters()).device
        inputs = {key: value.to(target_device) if hasattr(value, "to") else value for key, value in inputs.items()}
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=180, do_sample=False)
        generated = generated[:, inputs["input_ids"].shape[1] :]
        raw_text = processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
        parsed = parse_json(raw_text)
        output_rows.append({
            "schema": "robot_teleop.vlm-audit/v0.1",
            "timestamp_ns": anchor,
            "camera_ids": [camera for camera, _ in selected],
            "source_frame_timestamps_ns": {camera: int(row["timestamp_ns"]) for camera, row in selected},
            "model_id": "Qwen/Qwen2.5-VL-3B-Instruct",
            "model_path": str(args.model.resolve()),
            "prompt_schema": "teleop_visual_audit_v0.1",
            "raw_response": raw_text,
            "audit": parsed,
            "parse_valid": parsed is not None,
        })
        print(json.dumps({"timestamp_ns": anchor, "parse_valid": parsed is not None}), flush=True)
    if not output_rows:
        raise SystemExit("no audit rows generated")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output_rows), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "rows": len(output_rows), "cameras": cameras}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
