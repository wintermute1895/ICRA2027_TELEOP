# Causal Command Filter v0

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

When `executed_joint_command_rad` is unavailable, the trainer uses
`mapped_joint_command_rad` as its target. This supports integration testing
and action-prior experiments, but cannot by itself prove an improvement over
the existing rule filter. To learn a nontrivial correction, the dataset needs
at least one of: distinct executed-action labels, controlled command
perturbation/recovery data, or verified local reference-progress targets.
