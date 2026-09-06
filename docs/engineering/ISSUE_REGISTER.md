# Engineering issue register

This is the working boundary for the repository. The labels `correction` and
`recovery` are not treated as two ground-truth classes. Human annotation only
supervises a verified `correction_start`/`correction_end` interval. A recovery
key or VLM phrase is descriptive audit metadata; if its boundary is unclear,
the sample remains `A_audit`/hard-case and is not forced into training.

## Must fix now

### Basic engineering

- Keep one entry point per workflow: capture, flywheel, training, rollout.
- Never concatenate a path with an optional suffix; resolve a complete path once.
- Record commit, config hash, action contract, device, and output directory in
  every training/rollout manifest.
- Run ROS Python through the Jazzy environment wrapper and model training through
  the dedicated training environment.

### Code and interaction

- Plain teleoperation must subscribe directly to `/right_arm_joint_control`.
- Deployment supervisor must not be started for a plain teleoperation capture.
- ROS logger calls must use one formatted message, not stdlib printf arguments.
- New output directories must be timestamped and never silently overwritten.

### Data collection

- Preserve raw, filtered, executed, state, RGB, timestamps, terminal audit and
  correction intervals in each episode.
- Exclude failed, incomplete, black-frame, missing-frame and dimension-invalid
  episodes from positive training views, while retaining them for audit.
- Split by complete episode before making windows.
- Use `arm7` as the primary ACT contract; `arm7_hand6` is exploratory only.

## Fix next

- Make flywheel discovery use episode manifests rather than a single glob.
- Add deterministic train/validation/test manifests with held-out
  configuration IDs.
- Add one episode-level report combining action quality, gate metrics,
  intervention, clipping, fallback and data yield per operator-minute.
- Add nominal/correction sampling quotas so correction data cannot disappear
  as assisted captures become easier.

## Intentionally not a current hard gate

- `recovery` versus `correction` as separate labels: the distinction is not
  reliable enough for annotation. Keep optional recovery notes for analysis.
- Natural-language VLM semantics: retain them as mutable metadata; do not reject
  an episode because a phase description changed.
- SDK/vendor refactors: the safety boundary belongs between LinkerTA and the
  bridge; vendor packages remain untouched.

## Paper alignment

The paper's claim is selective, bounded assistance that increases admitted
`A_action` episodes per operator-minute without increasing nominal false
intervention or degrading unseen hard-case behavior. It is not a claim that the
system learns a separately measurable recovery class.
