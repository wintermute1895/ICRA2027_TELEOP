# Experiment Manifests

An experiment manifest is the immutable identity of one trial. It separates
exploratory changes from confirmatory comparison without hard-coding `A` or
`B` into control code. Conditions are versioned profiles and have a paper role:

| Condition ID | Role | Meaning |
|---|---|---|
| `nominal_reference_v1` | A | Nominal reference and safety projection only |
| `bc_all_v1` | B0 | Direct behavior cloning from all eligible demonstrations |
| `reference_residual_bc_v1` | B1 | Reference plus learned local residual |
| `reference_residual_dagger_v1` | B2 | B1 plus reviewed corrective aggregation |

Adding a new proposal means adding `*_v2.yaml`; never edit a profile that has
already been used for data collection.

## Task Family Boundary

The task base class is intentionally narrower than a generic robotics task:

```text
ContactRichPrecisionAssemblyTask
  -> ConnectorInsertionTask
    -> UsbCInsertionScenario
```

`ContactRichPrecisionAssemblyTask` covers nominal-reference-guided local
correction around alignment, contact, seating/insertion, verification and
recovery. It requires task-relative geometric and contact outcomes. It excludes
open-world navigation, unconstrained grasping, pure force-only tasks without a
geometric reference, and global replanning as the main research variable.

The connector child adds plug/receptacle/insertion-axis entities and insertion
depth, lateral, angular and stable-contact measurements. The USB-C child only
sets concrete dimensions, thresholds and perturbation ranges. New connectors
must add a child profile; they must not broaden or rewrite the recorded task
family after data collection.

The resolver supports `extends` and stores the SHA256 of every ancestor and
child profile. The resulting manifest contains the resolved child contract and
the full source chain, so replay never depends on mutable profile lookup.

## Create A Trial

The resolver expands task perturbation levels using a deterministic seed and
records every source profile SHA256. It does not launch ROS2 or MuJoCo.

```bash
/usr/bin/python3 tools/resolve_experiment_manifest.py \
  --condition config/conditions/reference_residual_bc_v1.yaml \
  --domain sim \
  --trial-seed 1250 \
  --target-pose-level hard \
  --occlusion-level long \
  --camera-bias-level strong \
  --contact-bias-level strong \
  --operator-id sim_operator_01 \
  --output evidence/manifests/reference_residual_bc_trial_1250.json
```

The task seed range determines `train`, `validation`, or `held_out`. Split by
trial, never by frame. A held-out seed must not enter training or corrective
aggregation.

## Capture

For a real capture, create the manifest with `--domain real`, then pass it to
the normal capture launcher. The launcher requires normal physical E-stop and
real-motion confirmations independently of the manifest.

```bash
bash scripts/start_capture_session.sh \
  --experiment-manifest=/absolute/path/to/real_trial.json \
  --real \
  --physical-estop-ready \
  --confirm=I_UNDERSTAND_REAL_ROBOT
```

`record_episode.sh` embeds the complete manifest and its SHA256 in
`artifacts/teleop_capture_manifest.json`. A manual `condition_id`, `task_id`,
or `operator_id` that conflicts with the manifest is rejected.

## Runtime Responsibility

`config/tasks/usb_c_insertion_v1.yaml` is the frozen task contract. The
MuJoCo adapter must consume the generated perturbation and emit these raw task
signals for every trial:

```text
nominal_reference
human_command
policy_residual
command_before_safety
executed_command
plug_tip_insertion_depth_m
lateral_error_m
angular_error_deg
stable_contact_duration_s
success
failure_mode
recovery_success
intervention
```

The profile alone does not implement success. Until the MuJoCo runtime writes
these signals, a trial is engineering exploration only and cannot enter the
paper's task-success comparison.
