#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CanonicalActMulticameraTest(unittest.TestCase):
    def test_projects_two_named_cameras_into_each_frame(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            streams = root / "canonical/streams"
            streams.mkdir(parents=True)
            controls = streams / "control.jsonl"
            controls.write_text("".join(json.dumps({
                "timestamp_ns": stamp,
                "robot": {"q_rad": [0.1]},
                "execution": {"controller_command": [0.2]},
            }) + "\n" for stamp in (10, 20)), encoding="utf-8")
            camera_stream = streams / "cameras.jsonl"
            camera_stream.write_text("", encoding="utf-8")
            manifest = root / "canonical/episode.manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "teleop_episode/v0.1",
                "episode_id": "two-cameras",
                "source": "real",
                "intended_uses": ["policy_training"],
                "configuration": {"configuration_id": "test", "split": "test"},
                "clock": {"alignment_tolerance_ns": 100},
                "streams": {
                    "control": {"storage_ref": "streams/control.jsonl"},
                    "cameras": {"recorded_frames": {
                        "availability": "available", "storage_ref": "streams/cameras.jsonl",
                    }},
                },
            }), encoding="utf-8")
            indexes = []
            for camera_id in ("main_rgb", "auxiliary_rgb"):
                image = root / f"{camera_id}.png"
                image.write_bytes(b"fixture")
                index = root / f"{camera_id}.jsonl"
                index.write_text("".join(json.dumps({
                    "timestamp_ns": stamp,
                    "camera_id": camera_id,
                    "reference": {"frame_reference": str(image)},
                }) + "\n" for stamp in (10, 20)), encoding="utf-8")
                indexes.append(index)
            command = [
                sys.executable, str(ROOT / "tools/canonical_episode_to_act_dataset.py"),
                "--manifest", str(manifest), "--output-dir", str(root / "act"),
            ]
            for camera_id, index in zip(("main_rgb", "auxiliary_rgb"), indexes):
                command.extend(("--camera-id", camera_id, "--camera-index", str(index)))
            subprocess.run(command, check=True, text=True, capture_output=True)
            rows = [json.loads(line) for line in (root / "act/episode_000000.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertIn("observation.images.main_rgb", rows[0])
            self.assertIn("observation.images.auxiliary_rgb", rows[0])
            projection = json.loads((root / "act/projection_manifest.json").read_text())
            self.assertEqual(projection["camera_ids"], ["main_rgb", "auxiliary_rgb"])


if __name__ == "__main__":
    unittest.main()
