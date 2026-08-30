# Canonical Episode Data Contract v0.1

Status: draft for W0/W1 implementation.  
Owners: iLeX (contract), W0 implementer (DexMimicGen adapter), real-data owner (recorder).  
Applies to: DexMimicGen/Robosuite simulation, real precision-insertion teleoperation, learned-filter training, and ACT/DP downstream studies.

## 1. Purpose and non-goals

This is the authoritative, lossless episode record for the project. It makes simulation and real data enter one validation and experiment-management path while retaining the causal signals required by the learned command filter.

It is not a claim that simulation and real data are physically interchangeable, and it is not the on-disk format required by a particular trainer. A LeRobot dataset is a documented projection of this contract for ACT/DP. The original canonical record remains the audit source.

The contract supports three data uses:

1. `filter_training`: requires complete causal command records and an `A_action` admission decision;
2. `policy_training`: requires the observation/action projection needed by ACT/DP;
3. `audit_only`: retains failed, unsafe, incomplete, or aborted episodes without treating them as positive action-learning data.

## 2. Core invariants

- Every episode has an immutable `episode_id`, `schema_version`, source, task configuration, and terminal audit. Geometry and calibration metadata are optional extensions.
- Every time-indexed stream uses signed 64-bit integer `timestamp_ns` in one declared monotonic clock domain. Array index is never treated as time.
- Units, action semantics, and controller frequency are explicit metadata. Frames and calibration are declared only when geometric streams are present.
- Missing causal fields are represented by `availability: unavailable` plus a reason. They must not be filled with zeroes, copied from another action field, or silently dropped.
- A physical episode records observed execution separately from desired/commanded actions. The causal order is `raw teleop -> filter output -> safety projection -> controller command -> observed robot state`.
- An `A_action` decision is a transparent gate. It is not a learned scalar data-quality score.

## 3. Episode envelope

Each canonical episode is stored as one HDF5 group/file plus an immutable JSON manifest. Video/image payloads may be external files, but are addressed by timestamped references in the manifest.

```text
schema_version                 "teleop_episode/v0.1"
episode_id                     UUID or stable content-addressed ID
source                          simulation | real
collection_mode                 generated | teleop_rule | teleop_learned | replay
intended_uses                  [filter_training, policy_training, audit_only]
task                            task_id, task_family, success_spec_version
configuration                  configuration_id, declared parameter values, split
clock                           clock_domain, control_hz, timestamp origin
frames                          optional named SE(3) frame conventions
calibration                     optional calibration and transform references
streams                         time-indexed observations, commands, execution, sensors
terminal_audit                 success, termination, safety, admission decision
data_integrity                 validator results and content hashes
provenance                     software, environment, source dataset/run, git revision
```

`source=simulation` includes DexMimicGen/Robosuite. `source=real` includes physical teleoperation and physical replay. `collection_mode` says how actions were produced; it must not be inferred from `source`.

## 4. Coordinate frames, units, and action semantics

All transforms use the form `T_AB`: coordinates expressed in frame `B` transformed into frame `A`. The following named frames are mandatory when applicable:

```text
B   robot base/world frame used by the controller
E   robot end-effector frame from forward kinematics
P   grasped part / plug insertion frame
R   receptacle / target frame
C_i camera optical frame for camera i
```

When a geometric estimator is available, task metadata may declare insertion convention and publish relative task state:

```text
T_RP = inverse(T_BR) * T_BE(q) * T_EP
```

SI units are mandatory: metres, radians, seconds, radians/second, metres/second, Newtons where available. Quaternion ordering, rotation-vector convention, joint order, and gripper normalization are declared in `action_spec` and may not vary within a dataset version.

The canonical policy action is normally a base-frame Cartesian delta command:

```text
u_canonical = [dx, dy, dz, rx, ry, rz, g]
```

where translation is metres over one control interval, rotation is an axis-angle rotation vector in radians, and `g` follows the declared gripper convention. A task may use a different action representation only with an explicit `action_spec`; the adapter must then provide a documented mapping to and from the canonical representation. Controller-native normalized actions are never the only stored action representation.

## 5. Time-indexed streams

The HDF5 payload uses append-only tables. Each table has its own timestamps; image streams do not need to be resampled to control rate.

### 5.1 Required episode-level metadata

```text
task.task_id
task.success_spec_version
configuration.configuration_id
configuration.parameters
clock.control_hz
action_spec
provenance.code_revision
```

`configuration.parameters` contains the declared configuration variables, e.g. target pose, part initial pose, robot start state, camera configuration, lighting/layout identifiers, and reset distribution bin. It must permit stratified train/test and coverage analysis without inspecting pixels.

### 5.2 Required control/state table: `streams/control`

One row per controller update, with:

```text
timestamp_ns
robot.q_rad
robot.dq_rad_s
robot.ee_pose_B                 [x, y, z, qx, qy, qz, qw]
execution.controller_command    canonical action actually sent to controller
execution.observed_action       optional estimate of achieved action
```

`robot.q_rad` is ordered using `robot.joint_names`. A simulator writes its ground-truth state here; real hardware writes measured state. `observed_action` is optional because it may require differentiated measurements, but its availability must be explicit.

### 5.3 Optional geometry/task-context table: `streams/task_context`

```text
timestamp_ns
target.pose_BR                  [x, y, z, qx, qy, qz, qw]
target.pose_confidence
target.visibility_valid
reference.progress              scalar or declared phase label
reference.valid
reference.collision_free
```

A target pose requires `target.pose_source` and its calibration reference. A moving camera or changing fixture does not invalidate an episode; omit this stream unless a valid estimator is available.

Simulation may provide ground truth poses but must label `pose_source=sim_ground_truth`. Physical records should retain estimator confidence and raw estimator diagnostics in `streams/estimator`.

### 5.4 Sensor tables: `streams/cameras/<camera_id>`

```text
timestamp_ns
frame_reference                 relative image/video path or HDF5 dataset index
encoding, width, height
intrinsics_version
extrinsics_version
valid
```

At least one declared camera must be available for policy-training episodes. Cameras are named rather than positional (`external_rgb`, `wrist_rgbd`, etc.). RGB-D depth, force/torque, tactile, or external estimator streams are optional extensions with their own timestamps and `valid` flags.

### 5.5 Causal command table: `streams/commands`

```text
timestamp_ns
raw_teleop.value                canonical action from the operator/master device
filter_output.value             learned/rule filter output before safety projection
safety_projected.value          command after fixed safety projection
controller_command_ref          pointer to the control-table row sent to the robot
raw_teleop.availability
filter_output.availability
safety_projected.availability
```

For true teleoperation, all three command stages are required to train a causal filter. For generated simulation trajectories such as DexMimicGen, `raw_teleop` and `filter_output` are normally `unavailable`, with reason `not_recorded_by_source`; the generated action may still populate `safety_projected` and `execution.controller_command` where semantically valid.

### 5.6 Event table: `streams/events`

Events are sparse and timestamped:

```text
safety_violation | estop | collision_warning | target_lost |
manual_override | external_assistance | reset | synchronization_fault |
reference_invalid | terminal_success | terminal_failure | abort
```

Each event has `timestamp_ns`, severity, source, and an optional structured payload. Any unlogged external intervention invalidates `A_action` admission.

## 6. Terminal audit and data buffers

Every episode receives exactly one terminal audit record:

```text
terminal.success
terminal.termination_reason
terminal.safety_violation
terminal.unlogged_external_override
data_integrity.complete_causal_record
data_integrity.synchronization_valid
audit.buffer                     A_action | A_audit
audit.admission_rule_version
audit.failed_gates               ordered list
```

Initial `A_action` admission is:

```text
valid_task_configuration
AND complete_causal_record
AND successful_terminal_insertion
AND no_safety_violation
AND no_unlogged_external_override
```

`complete_causal_record` means that each required control interval can align raw teleoperation input, filter output, safety-projected command, controller command, and measured robot state under the synchronization tolerance in `clock`. Task context, TCP pose, insertion depth, tactile, and derived observed action are optional extensions. Successful safety recovery, failed episodes, sensor loss, manual recovery, and invalid configurations remain in `A_audit`; they are not discarded.

For `policy_training` only, a source dataset may be usable despite unavailable teleoperation fields. It must never be relabelled as `A_action` for `filter_training` merely because its terminal state is successful.

## 7. Dataset views and LeRobot projection

The canonical store is projected into a trainer-specific view with a versioned mapping file.

Minimum ACT/DP projection:

```text
observation.images.<camera_id>  <- streams/cameras/<camera_id>
observation.state               <- robot state selected by action_spec
action                           <- execution.controller_command or declared canonical action
next.done / episode_index       <- terminal and episode boundaries
metadata                         <- configuration_id, source, schema version, split
```

The projection records image resize/crop, action normalization statistics, camera selection, resampling method, and excluded episodes. Normalization statistics are fit on the training split only. Train/validation/test splits are assigned by episode and configuration bin, never by independent frames.

ACT/DP does not consume `raw_teleop`, `filter_output`, safety events, or audit notes unless an explicitly versioned experiment says otherwise. Those fields remain available for diagnostics and filter learning.

## 8. Source adapters

### 8.1 DexMimicGen / Robomimic adapter

The W0 adapter must write:

- source metadata, simulator/asset version, task name, reset distribution and seed;
- observations, images, actions, robot state, terminal success and source timestamps where available;
- an explicit `action_spec` describing the Robosuite controller action;
- `unavailable` causal fields with `not_recorded_by_source` reasons;
- a `policy_training` intended use only, unless an independently collected raw command chain is present.

The adapter must not claim physical calibration, real safety events, or `A_action` eligibility.

### 8.2 Physical teleoperation recorder

The W3 recorder must write each causal command stage before transmission, measured robot state after transmission, sensor timestamps, and all operator/safety events. Target estimators, calibration, tactile, and geometry are recorded when available, but are not prerequisites for collection or `A_action`.

## 9. Validation gates

A dataset validator must reject or quarantine an episode when any of these fail:

1. required core metadata or action specification is missing; declared geometry is validated only when present;
2. timestamps are non-monotonic, duplicated beyond policy, or outside the declared alignment tolerance;
3. state/action dimensions, units, joint order, or action range contradict `action_spec`;
4. image references are missing, unreadable, or cannot be aligned to their timestamp;
5. terminal audit contradicts the event log;
6. a record claims `filter_training` or `A_action` without a complete causal command chain;
7. a present geometric stream lacks its declared pose source or calibration reference;
8. a train/test split mixes frames from the same episode or violates a declared configuration holdout.

The validator produces a machine-readable report attached to `data_integrity.validator_report_ref`. Validation failure does not delete the source record; it routes the episode to `A_audit` or quarantine with the failure reasons.

## 10. Versioning and migration

- `schema_version` changes only for incompatible semantic or structural changes.
- Additive optional fields are allowed in v0.1 but must be listed in the manifest.
- Every adapter and validator writes its code revision and configuration hash.
- No adapter overwrites canonical raw data. Corrections create a new derived dataset version with parent IDs and migration notes.
- RunEvidence records canonical dataset version, projection version, code revision, training configuration, checkpoint, and deployment/evaluation run ID.

## 11. Immediate implementation checklist

1. Implement the JSON Schema in `schemas/teleop_episode_v0_1.schema.json`.
2. Implement a narrow DexMimicGen Can Sorting adapter and validator fixture for W0.
3. Implement a LeRobot projection manifest; do not make the projection the sole record.
4. Wire the real teleoperation logger to `streams/commands`, `streams/control`, and `streams/events` before collecting D0. Add `streams/task_context` only after an estimator is trustworthy.
5. Freeze the filter-specific action representation in W2 before training `F_static`.
