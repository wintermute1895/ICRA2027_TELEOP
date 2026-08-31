#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class AttachVlmEmbeddingsTest(unittest.TestCase):
    @staticmethod
    def episode_row(stamp):
        return {
            "header_stamp_ns": stamp,
            "success": True,
            "master_joint_raw": [0.0, 0.0],
            "robot_joint_state_rad": [0.0, 0.0],
            "residual_target_rad": [0.01, -0.01],
        }

    def test_aligns_frozen_embedding_and_records_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "episode.jsonl"
            episode.write_text("".join(json.dumps(self.episode_row(stamp)) + "\n" for stamp in (100, 200)))
            embeddings = root / "embeddings.jsonl"
            embeddings.write_text("".join(json.dumps({"timestamp_ns": stamp, "camera_id": "main_rgb", "embedding": [0.1, 0.2]}) + "\n" for stamp in (90, 190)))
            output = root / "with_vlm.jsonl"
            subprocess.run([
                sys.executable, str(ROOT / "tools/attach_vlm_embeddings.py"),
                "--episode", str(episode), "--embeddings", str(embeddings),
                "--output", str(output), "--model-id", "test-vlm", "--model-revision", "r1",
                "--camera-id", "main_rgb",
            ], check=True, text=True, capture_output=True)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(rows[1]["vlm_embedding"], [0.1, 0.2])
            manifest = json.loads(output.with_suffix(output.suffix + ".manifest.json").read_text())
            self.assertEqual(manifest["embedding_dim"], 2)
            self.assertEqual(manifest["model_id"], "test-vlm")

    def test_one_combined_embedding_file_supports_two_cameras(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "episode.jsonl"
            episode.write_text(json.dumps(self.episode_row(100)) + "\n")
            embeddings = root / "embeddings.jsonl"
            embeddings.write_text("".join([
                json.dumps({"timestamp_ns": 90, "camera_id": "main_rgb", "embedding": [0.1, 0.2]}) + "\n",
                json.dumps({"timestamp_ns": 95, "camera_id": "auxiliary_rgb", "embedding": [0.3, 0.4]}) + "\n",
            ]))
            output = root / "with_vlm.jsonl"
            subprocess.run([
                sys.executable, str(ROOT / "tools/attach_vlm_embeddings.py"),
                "--episode", str(episode), "--embeddings", str(embeddings),
                "--output", str(output), "--model-id", "test-vlm",
                "--camera-id", "main_rgb", "--camera-id", "auxiliary_rgb",
            ], check=True, text=True, capture_output=True)
            row = json.loads(output.read_text().strip())
            self.assertEqual(row["vlm_embedding"], [0.1, 0.2, 0.3, 0.4])

    def test_rejects_missing_explicit_residual_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            episode = root / "episode.jsonl"
            row = self.episode_row(100)
            row.pop("residual_target_rad")
            episode.write_text(json.dumps(row) + "\n")
            embeddings = root / "embeddings.jsonl"
            embeddings.write_text(json.dumps({
                "timestamp_ns": 90, "camera_id": "main_rgb", "embedding": [0.1, 0.2]
            }) + "\n")
            result = subprocess.run([
                sys.executable, str(ROOT / "tools/attach_vlm_embeddings.py"),
                "--episode", str(episode), "--embeddings", str(embeddings),
                "--output", str(root / "output.jsonl"), "--model-id", "test-vlm",
            ], text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("residual_target_rad", result.stderr)


if __name__ == "__main__":
    unittest.main()
