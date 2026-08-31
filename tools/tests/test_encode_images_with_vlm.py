#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from tools.encode_images_with_vlm import frame_reference, load_frame_rows, resolve_local_model


class EncodeImagesWithVlmTest(unittest.TestCase):
    def test_loads_two_named_camera_indexes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            indexes = []
            for camera_id in ("main_rgb", "auxiliary_rgb"):
                path = root / f"{camera_id}.jsonl"
                path.write_text(json.dumps({
                    "timestamp_ns": 1,
                    "camera_id": camera_id,
                    "reference": {"frame_reference": f"frames/{camera_id}.png"},
                }) + "\n")
                indexes.append(path)
            rows = load_frame_rows(indexes, ["main_rgb", "auxiliary_rgb"])
            self.assertEqual([row[1]["camera_id"] for row in rows], ["main_rgb", "auxiliary_rgb"])
            self.assertEqual(frame_reference(rows[0][0], rows[0][1]), root / "frames/main_rgb.png")

    def test_rejects_mismatched_camera_contract(self):
        with self.assertRaises(ValueError):
            load_frame_rows([Path("one.jsonl")], ["main_rgb", "auxiliary_rgb"])

    def test_resolves_revision_to_immutable_local_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            repository = cache / "models--google--model"
            (repository / "refs").mkdir(parents=True)
            (repository / "refs/main").write_text("abc123\n")
            snapshot = repository / "snapshots/abc123"
            snapshot.mkdir(parents=True)
            source, revision = resolve_local_model("google/model", "main", cache)
            self.assertEqual(Path(source), snapshot)
            self.assertEqual(revision, "abc123")


if __name__ == "__main__":
    unittest.main()
