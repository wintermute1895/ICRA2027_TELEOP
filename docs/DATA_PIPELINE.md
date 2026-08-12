# Data Pipeline

This pipeline keeps simulation and hardware data semantically identical. Both
paths record ROS2 messages, export per-arm canonical JSONL, run the same data
quality gate, and then enter the same offline kinematic/collision evaluator.
DexCatch is only that offline evaluator; it is never inserted in the realtime
teleoperation control path.

```text
shared teleop command topics -> simulation MuJoCo mirror or real driver
ROS2 bag -> canonical left/right JSONL -> data-quality gate -> offline evaluator -> A/B aggregation
```

The final actuator endpoint is the only intended distinction:

| Concern | Simulation | Hardware |
|---|---|---|
| Arm state | `/sim/robot1/<arm>_arm/joint_states` | `/robot1/<arm>_arm/joint_states` |
| Head RGB/depth | `/sim/camera/camera/...` | `/camera/camera/...` |
| Teleop mapped command | `/teleop/<arm>/mapped_joint_command` | same topic and unit |
| Actuator endpoint | `sim_robot_driver` / MuJoCo | `lbot_driver` / official SDK and CAN |
| Export and scoring | identical tools | identical tools |

Hand topics can be recorded as additional canonical fields after the recorder
and exporter are extended together. They must not change the existing arm field
units: arm joint commands and states remain radians; LinkerHand command values
use the SDK's documented `[0,255]` scale.

## Record

Use the capture launcher for a real episode. It performs the preflight checks,
starts the ROS graph, writes a RunEvidence directory, and records a rosbag.
Real motion still requires its explicit E-stop and confirmation arguments.

For simulation, record the same field contract with simulation namespaces:

```bash
SOURCE_DOMAIN=sim \
ROBOT_STATE_NAMESPACE=/sim/robot1 \
CAMERA_NAMESPACE=/sim/camera/camera \
SIM_CAMERA_NAMESPACES=/sim/camera/left_wrist,/sim/camera/right_wrist \
TELEOP_NAMESPACE=/teleop \
bash scripts/record_episode.sh
```

The recorder must be started only after the state and camera topics are alive.
The quality gate intentionally detects cases where robot state begins before
the first camera frame.

## Export And Gate

Use the system ROS Python, not a Conda Python. ROS2 Humble's Python extension
is built for Python 3.10; a Python 3.12 Conda process cannot import it.

Current real bags use `/teleop`. Historical bags recorded before the rename use
`/vist`, which must be declared explicitly:

```bash
bash scripts/export_episode.sh \
  --bag evidence/teleop/<episode>/artifacts/rosbag2 \
  --source-domain real \
  --teleop-namespace /teleop \
  --output-dir evidence/teleop/<episode>/derived
```

```bash
bash scripts/export_episode.sh \
  --bag evidence/teleop/20260809T063235Z_teleop-episode-1_6add5e/artifacts/rosbag2 \
  --source-domain real \
  --teleop-namespace /vist \
  --output-dir /tmp/legacy-episode-derived
```

For simulation the only necessary change is `--source-domain sim`; the script
selects `/sim/robot1` and `/sim/camera/camera` by default:

```bash
bash scripts/export_episode.sh \
  --bag evidence/sim/<episode>/artifacts/rosbag2 \
  --source-domain sim \
  --output-dir evidence/sim/<episode>/derived
```

The exporter is read-only. File-level zstd rosbag files are expanded to a
temporary directory under `/tmp` and removed after parsing; image pixels remain
in the source rosbag and JSONL keeps timestamped references only.

Each output directory contains:

```text
left_episode.jsonl
left_episode.jsonl.manifest.json
left_data_quality.json
right_episode.jsonl
right_episode.jsonl.manifest.json
right_data_quality.json
```

Each state-aligned JSONL record includes raw master input, One-Euro filtered
master input, mapped arm command, measured arm state, and nearest RGB/depth
frame references when their source topics exist. A missing source topic is
listed in the export manifest; no absent signal is synthesized.

`quality_gate=pass` means the episode is complete enough for analysis. A
`review` result is retained with exact reasons and does not mean task failure.
It must be resolved or explicitly excluded before A/B aggregation.

## Offline Evaluation And A/B Analysis

For each per-arm JSONL that passes the data-quality gate, run the offline
kinematic evaluator using the matching robot URDF and the same safety margins:

1. Recompute FK/TCP trajectory and command-state tracking error.
2. Check URDF joint limits, singularity metric, and collision clearance over
   the replayed path.
3. Attach the evaluator report and human/task success label to the episode.
4. Aggregate only predeclared metrics by `condition_id` using the experiment
   profile in `config/experiments/precision_assembly_ab.yaml`.

The task-success and insertion/contact evaluator is intentionally separate from
this pipeline until the dedicated scene asset and collision contract is ready.
See `docs/EXPERIMENT_AND_SCORING.md` for metrics and statistical design.

## Data Flywheel

The core algorithm loop is offline and conservative. It cannot command a robot:

```text
episode -> data-quality gate -> trajectory evaluator -> hard-case miner
        -> registry -> A/B aggregate -> next-round replay/collection plan
```

For every exported arm JSONL, generate the control-quality and hard-case
reports. This is the same command for real and simulation data:

```bash
/usr/bin/python3 tools/evaluate_trajectory_quality.py \
  --episode <derived>/left_episode.jsonl \
  --output <derived>/left_trajectory_quality.json

/usr/bin/python3 tools/mine_hard_cases.py \
  --trajectory-report <derived>/left_trajectory_quality.json \
  --output <derived>/left_hard_cases.json
```

Then build the cross-domain registry, aggregate predeclared A/B metrics, and
produce a recommendation-only next-round plan:

```bash
/usr/bin/python3 tools/build_episode_registry.py \
  --root evidence/teleop \
  --root evidence/sim \
  --output reports/data_flywheel/episode_registry.jsonl

/usr/bin/python3 tools/aggregate_ab_results.py \
  --registry reports/data_flywheel/episode_registry.jsonl \
  --output reports/data_flywheel/ab_report.json

/usr/bin/python3 tools/plan_data_flywheel.py \
  --registry reports/data_flywheel/episode_registry.jsonl \
  --output reports/data_flywheel/next_round.json
```

The registry treats an episode as analysis eligible only if both its data and
trajectory gates pass. The planner prioritizes failed quality records for
repair, failed trajectory records for shadow replay, and valid hard-case
segments for targeted coverage. `condition_id` comes from the capture manifest;
exports outside a RunEvidence directory remain `unassigned` and are excluded
from A/B aggregates.
