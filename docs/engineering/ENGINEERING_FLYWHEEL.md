# Engineering flywheel

The stable path is:

```text
capture run / rosbag2 -> aligned export -> quality gate -> canonical
-> correction mask -> frozen dual-camera VLM view -> episode split
-> GPU filter training -> evaluation -> explicit runtime promotion
```

The filter model is correction-aware rather than residual-only. It trains on
both nominal and corrective windows, predicts a correction probability, and
uses residual composition only at deployment:

```text
u_raw + p(correction) * alpha * (u_expert_hat - u_raw)
```

Nominal windows remain in the dataset and receive a small zero-residual
regularizer; corrective windows receive higher action weight and gate labels.

## One run

```bash
bash scripts/run_flywheel.sh \
  /media/ilex/Cyan_data/ICRA2027_TELEOP_DATA/evidence/teleop/<run>
```

The command accepts a capture directory or its `artifacts/rosbag2` directory.
Derived output is written below `<run>/derived/flywheel_v1/`; source evidence is
read-only. Use the Python entry point with `--prepare-only` to stop before
training.

## Batch preparation and training

```bash
bash scripts/run_flywheel_batch.sh --prepare-only
bash scripts/run_flywheel_batch.sh
```

The batch selector requires a bag, capture manifest, terminal audit, and human
event stream. It admits only `success=true`,
`safety_violation=false`, and `unlogged_external_override=false`. Task and
phase names remain free-form metadata.

## Output

Each run contains `derived/flywheel_v1/` with export JSONL, quality report,
decoded camera frames, canonical manifest, filter JSONL, correction view, VLM
view, and `pipeline_state.json`. Training rounds are stored in the configured
`storage.run_root` and include a checkpoint, evaluation report, round manifest,
and TensorBoard events.

## Runtime boundary

ACT and the learned filter are candidate producers. Both feed the single
`model_deployment_supervisor`, which handles shadow/active mode, freshness,
shape, finite-value, delta and step checks, and immediate fallback to LinkerTA.
Only the supervisor output is connected to `teleop_control_bridge`. The bridge
remains responsible for mapping, direction signs, One-Euro filtering, limits,
arming, and hardware publication. SDK/vendor packages are not part of this
path; see `docs/engineering/MODEL_DEPLOYMENT.md`.

## Rollout evaluation

Every recorded rollout uses the same canonical topic contract as a capture.
Run the read-only evaluator after stopping the rollout:

```bash
bash scripts/evaluate_model_rollout.sh --bag /media/ilex/Cyan_data/ICRA2027_TELEOP_DATA/rollouts/<timestamp>
```

The evaluator exports the arm stream and writes `reports/data_quality.json`,
`reports/trajectory_quality.json`, and `rollout_evaluation.json`. It never
publishes ROS commands and never accesses hardware.

## Human gates

- Review terminal success/failure and correction intervals. Treat recovery as
  optional audit notes, not a separate training class or admission gate.
- Hold out episodes before checkpoint promotion.
- Enable a promoted runtime config explicitly for a later capture.
- Keep physical E-stop and real-hardware confirmation outside automation.

## Troubleshooting

Check the external disk with:

```bash
findmnt -M /media/ilex/Cyan_data -t exfat -o SOURCE,TARGET,FSTYPE,OPTIONS
```

It must be `rw`. ROS bag tools run through
`skills/ros2-python-env/scripts/run_ros2_python.sh`, which loads Jazzy and the
workspace overlay. GPU training requires `torch.cuda.is_available() == True`;
a sandbox that cannot see the GPU is an environment limitation.
