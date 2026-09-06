# Causal Command Filter v0

> Scope: this document describes the earlier linear ridge baseline. Its
> executed-action requirement does not apply to the current Transformer-CVAE
> trajectory model in `src/teleop_filter/`, which trains against an explicit
> `residual_target_rad`; controller commands are not silently used as residuals.

This is the first deployable experiment artifact for the learned filter
hypothesis. It is intentionally a small linear ridge action prior rather than
a claim that a particular neural architecture is the contribution.

## Contract

At time `t`, the model consumes only a bounded history of mapped joint
commands and the current robot joint state. It predicts an action prior from
episodes admitted by the frozen task audit:

```text
history(mapped command) + state -> a_theta
mapped command + bounded confidence-gated correction -> FollowJoint
```

It does not consume future frames, terminal labels, or human annotations at
runtime. `success: true` is used only offline to admit training records.

The online command is:

```text
a_t = mapped_t + alpha_t * clip(a_theta(history, state) - mapped_t)
alpha_t = blend * clamp(1 - ood_z / max_ood_z, 0, 1)
```

Invalid data, an incomplete history, or `ood_z >= max_ood_z` yields the
unmodified mapped command. The filter runs only in the simulation launch and
publishes to `/filter_v0`; it cannot share a topic with the hardware driver.

## Training Interpretation

`executed_joint_command_rad` is mandatory for training. A safety-projected
command is still a command, not a record of robot execution, and is never
substituted as a target. Missing execution observations are routed to audit or
policy views rather than silently entering filter training. To learn a
nontrivial correction, the dataset needs distinct executed-action labels,
controlled command perturbation/recovery data, or verified local
reference-progress targets.


## Canonical v0.1 projection

When the source is a canonical `teleop_episode/v0.1` manifest, first project materialized control, command, and task-context streams:

```bash
python3 tools/canonical_episode_to_filter_jsonl.py \
  --manifest episode.manifest.json \
  --output derived/filter_training.jsonl
```

The adapter resolves control, command, and available task-context streams from
the manifest. Explicit stream arguments remain available only as overrides.

The adapter requires the manifest terminal audit to be `A_action` and retains
raw, filter, safety-projected, executed, state, and optional `filter_context`
fields. The shared 8-value context contract is defined in
`config/filters/causal_command_filter_v0_1.json`: target pose in the
receptacle frame, progress, then visibility. Simulation publishes it only from
real MuJoCo task sites; real acquisition must provide the same ordering with
estimator confidence and calibration metadata in the canonical stream. Train
with `--context-size N` only when every accepted row has exactly N context
values; missing context is rejected, never zero-filled.

## Flywheel Round Training

`legacy/causal_command_filter_v0/train_flywheel_round.py` trains one immutable simulation-only filter
round from a JSON config. It projects only canonical `A_action` episodes using
the strict adapter, preserves episode-level train/validation splits, and writes
a model plus a report containing round lineage, input episode IDs, config/code
hashes, rejected episodes, and offline prediction metrics.

```bash
python3 legacy/causal_command_filter_v0/train_flywheel_round.py \
  --round-config config/filters/flywheel_round.example.json \
  --output-dir runs/filter/F_static_d0_v1
```

Use a new config for `F_flywheel`, set `parent_round_id` to the accepted prior
round, and do not reuse its validation episodes as training input.
