# Model deployment boundary

ACT and the learned filter publish `JointState` candidates only. A single
deployment supervisor selects or rejects candidates and republishes one topic
for the bridge; no model process touches the SDK or vendor driver.

```text
LinkerTA raw ───────────────┐
ACT candidate ───────> model_deployment_supervisor ──> teleop_control_bridge ─> lbot_driver
filter candidate ────┘          |                         (mapping, limits, armed gate)
                                └─ diagnostics / fallback
```

Shadow mode always selects the raw fallback while recording decisions. Active
mode accepts a candidate only when it is fresh, finite, dimensionally correct,
within the configured offset, and within the per-frame step limit. Every
rejection falls back immediately.

Start the boundary safely:

```bash
bash scripts/start_model_deployment.sh config/runtime/model_deployment.yaml --shadow
```

Start a candidate producer with the same boundary:

```bash
bash scripts/start_model_deployment.sh config/runtime/model_deployment.yaml \
  --source=filter --filter-config=config/runtime/learned_filter.yaml --shadow
bash scripts/start_model_deployment.sh config/runtime/model_deployment.yaml \
  --source=act --act-config=config/runtime/act.yaml --shadow
```

Active mode is an explicit promotion step after held-out evaluation and a
shadow run:

```bash
bash scripts/start_model_deployment.sh config/runtime/model_deployment.yaml \
  --source=filter --filter-config=config/runtime/learned_filter.yaml \
  --active --confirm=I_UNDERSTAND_MODEL_DEPLOYMENT
```

This does not arm the robot. The bridge still owns `armed`, first MoveJ,
direction mapping, One-Euro filtering and joint limits. Real hardware requires
the existing physical E-stop and real-robot confirmation separately.

At the ROS boundary, `JointState.position` is LinkerTA degrees. The supervisor
checks radians internally and emits degrees to the bridge. ACT and filter
checkpoints require matching SHA-256; semantic labels remain metadata, while
shape, finite values, timestamps and checkpoint provenance are technical gates.

Diagnostics are JSON on `/model_deployment/diagnostics`, including `accepted`,
`source`, and rejection reasons such as `candidate_stale_or_missing`,
`candidate_invalid`, `candidate_delta_exceeded`, and `candidate_step_exceeded`.

## Complete rollout entry

Once a checkpoint and its SHA-256 have been promoted into the ACT/filter
runtime config, the complete hardware graph is started with one command:

Create that config without editing a shared file:

```bash
bash scripts/promote_model_checkpoint.sh --kind filter \
  --checkpoint /media/ilex/Cyan_data/ICRA2027_TELEOP/filter_runs/<round>/model/trajectory_filter.pt \
  --output /media/ilex/Cyan_data/ICRA2027_TELEOP/config/filter-promoted-<round>.yaml
```

```bash
bash scripts/start_model_rollout.sh --config config/runtime/rollout.yaml --shadow
```

The promoted config can be supplied for one rollout without changing
`config/runtime/rollout.yaml`:

```bash
bash scripts/start_model_rollout.sh --source filter \
  --filter-config /media/ilex/Cyan_data/ICRA2027_TELEOP/config/filter-promoted-<round>.yaml \
  --shadow
```

This starts the configured D435i cameras, candidate worker/adapter, deployment
supervisor, LinkerTA, lbot driver, and bridge. Add `--record-dir PATH` to save a
rosbag containing raw input, model output, diagnostics, robot state, pose,
vendor command, RGB and aligned depth streams. Stop with Ctrl-C; all process
groups are stopped in reverse order and the rollout manifest is written next to
the bag.

Evaluate a completed recording with the same topic contract:

```bash
bash scripts/evaluate_model_rollout.sh --bag /media/ilex/Cyan_data/ICRA2027_TELEOP_DATA/rollouts/<timestamp>
```

This performs a read-only rosbag export and writes data-quality and offline
trajectory-quality reports beside the bag. A review result is not a task
success authorization or permission to arm hardware.

For real active control, all confirmations are required:

```bash
bash scripts/start_model_rollout.sh --config config/runtime/rollout.yaml \
  --active --real --physical-estop-ready \
  --confirm=I_UNDERSTAND_REAL_ROLLOUT \
  --model-confirm=I_UNDERSTAND_MODEL_DEPLOYMENT
```

The command intentionally refuses a real armed rollout in shadow mode or
without both confirmations. It does not start hand CAN control; hand control
remains an independent, explicitly armed operation with its own CAN ownership
check.
