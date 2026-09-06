---
name: act-data-prep
description: Prepare recorded robot teleoperation episodes for ACT training. Use when converting rosbag evidence to canonical or LeRobot data, checking RGB/action timestamps, filtering failed or corrupt episodes, building episode-level train/validation splits, or diagnosing camera alignment.
---

# ACT Data Preparation

Use this skill for the complete, reproducible path from `evidence/teleop/<episode>` to an ACT-ready dataset. Never mutate raw rosbag or raw audit evidence; all reviewed or projected data must be written under `derived/` or a separate output root.

## Workflow

1. Enumerate candidate episode directories and read `artifacts/teleop_capture_manifest.json`, `terminal_audit.json`, and `capture_validation.json`.
2. Admit only episodes whose reviewed terminal audit has `success=true`, no safety violation, and no unlogged external override. Keep failed episodes in an audit-only/quarantine list.
3. Export each admitted rosbag to the canonical episode format using the repository exporter. Preserve message header timestamps and record the bag/export hashes.
4. Run timestamp diagnostics before projection. Match each RGB frame to the nearest action/state sample using ROS nanosecond timestamps and a configured maximum age; reject missing, non-monotonic, or over-age matches. Never align by row index.
5. Validate image references: file exists, decodes as RGB, dimensions are consistent, and reject black/near-black frames and long frame gaps.
6. Validate action/state vectors: finite numeric values, fixed dimensions, expected units, and monotonic timestamps. Reject an episode on any schema or dimension violation.
7. Split by episode (or task condition/scene group), never by frame. Store the split manifest with episode IDs, source hashes, task revision, camera order, and random seed.
8. Convert only the admitted projection to LeRobot/ACT format. Run a loader smoke test that reads one batch and verifies image, state, action, and timestamp shapes.
9. Train the first ACT smoke run on GPU when available. Use `--device cuda` and fail fast when CUDA is required; CPU is only for pipeline smoke tests.

## Repository Entry Points

- `tools/export_rosbag_episode.py`: rosbag to timestamped exported episode.
- `tools/validate_capture_artifacts.py`: capture artifact integrity gate.
- `tools/diagnose_time_sync.py`: camera/robot clock diagnostics.
- `tools/canonical_episode_to_act_dataset.py`: canonical episode to ACT/LeRobot projection.
- `tools/act_jsonl_to_lerobot.py`: JSONL conversion and schema projection.
- `tools/build_vlm_temporal_windows.py`: timestamped temporal windows for visual auditing; use `--causal` for online-compatible windows.

Read [references/quality-gates.md](references/quality-gates.md) before running a batch. Do not train on a directory merely because rosbag export succeeded; admission, timestamp, image, and action gates are separate.
