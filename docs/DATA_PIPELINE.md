# Data Pipeline

This pipeline keeps simulation and hardware capture semantically aligned. Both
paths record ROS2 messages, export derived per-arm `robot_teleop.episode/v1`
JSONL, run the same data-quality gate, and then enter the same offline evaluator.
DexCatch is only that offline evaluator; it is never inserted in the realtime
teleoperation control path.

```text
shared teleop command topics -> simulation MuJoCo mirror or real driver
ROS2 bag -> derived episode/v1 JSONL -> data-quality gate -> offline evaluator -> A/B aggregation
```

The final actuator endpoint is the only intended distinction:

| Concern | Simulation | Hardware |
|---|---|---|
| Arm state | `/sim/robot1/<arm>_arm/joint_states` | `/robot1/<arm>_arm/joint_states` |
| Head RGB/depth | `/sim/camera/camera/...` | `/camera/camera/...` |
| Teleop mapped command | `/teleop/<arm>/mapped_joint_command` | same topic and unit |
| Actuator endpoint | `sim_robot_driver` / MuJoCo | `lbot_driver` / official SDK and CAN |
| Export and scoring | identical tools | identical tools |

For real capture, the recorder additionally records LinkerHand force, matrix
pressure, and matrix-mass topics. Simulation intentionally records none of
these topics yet; its capture manifest declares `not_integrated_in_simulation`.
Arm joint commands and states remain radians; LinkerHand command values use the
SDK's documented `[0,255]` scale.

The export is not the `teleop_episode/v0.1` canonical record. It is an
immutable, read-only source for the canonical adapter. It may support
`audit_only` or an ACT/LeRobot projection after its adapter validates the
available fields; it must not be called `A_action` or used for `filter_training`
until it has a v0.1 manifest, task context, terminal audit, and complete
`raw -> filter -> projected -> executed` causal chain.

## Record

Use the capture launcher for a real episode. It performs the preflight checks,
starts the ROS graph, writes a RunEvidence directory, and records a rosbag.
Real motion still requires its explicit E-stop and confirmation arguments.
For real capture, SocketCAN interfaces must be brought up before starting this
launcher. The launcher checks their live state and exits with a repair command
instead of allowing the vendor LinkerTA node to block on an interactive sudo
prompt. Do not put a sudo password in a project config or capture manifest.

For repeated real collection, keep the teleoperation graph alive and use
manual episode segments. The recorder window then uses Enter to start an
episode, Enter again to stop and finalize its rosbag, asks for the terminal
audit, and returns to the next episode without restarting the robot, LinkerTA,
or cameras. `--episodes=0` keeps this loop available until `q` is entered at
the start prompt. This is the preferred interactive workflow; Ctrl-C remains
an emergency interruption, not the normal way to end a data segment.

The recorder window handles both operator control and second-person annotation,
so no tmux window switch is needed. Enter starts/stops an episode; digit keys
are immediate and do not require Enter: `1` approach, `2` align, `3` short insert, `4`
correction start/end, `5` stalled/misaligned, `6` recovery start, `7` target
lost, `8` retreat, `9` success, and `0` failure. Events are accepted only while
an episode is recording. Every event carries wall-clock, monotonic, and bag
receipt timestamps (the sidecar's `timestamp_ns` is the capture wall clock) and is stored both on `/teleop/events` and in
`artifacts/audit_events.jsonl`. Configure the de-identified auditor with
`CAPTURE_AUDITOR_ID` or `--auditor-id`.

The Python recorder exclusively owns this TTY. The rosbag subprocess is started
with keyboard controls disabled and stdin connected to `/dev/null`; it cannot
consume annotation digits, Enter, or change the recorder's terminal settings.

## Independent Hand Presets

Hand actuation is a separate process and terminal. It does not share the
recorder's keyboard, so auditor digits and Enter retain their capture semantics.
For the installed O6, the active controller reuses the same direct `linkerbot`
backend as `tools/hand_gesture_player.py`. It is the sole CAN owner and also
publishes ROS command evidence, normalized O6 feedback, and binary gripper
state. The official LinkerHand ROS SDK remains available for passive/other-model
integration, but is not in this O6 actuation path because it did not recognize
the installed firmware.

The lower-level `run_hand_preset_controller.sh` ROS backend is only for a
separately validated, already-running `hand_adapter` deployment:

```bash
scripts/run_hand_preset_controller.sh \
  --execute --physical-estop-ready \
  --confirm EXECUTE_HAND_PRESET_WITH_ESTOP_READY
```

For the installed right-hand O6, use the direct controller instead:

```bash
scripts/start_hand_control_session.sh --can=can1 \
  --physical-estop-ready --confirm=I_UNDERSTAND_REAL_HAND
```

It requires valid six-axis O6 feedback before accepting `f` and publishes
`/robot1/right_hand/joint_states` itself.
With `--can=auto` (the default), it reads LinkerTA's retained
`/linkerta/can_interface` announcement and selects the other UP CAN interface;
it never probes CAN buses by sending hand frames. If LinkerTA is not running,
pass the verified hand interface explicitly, for example `--can=can1`.
Start this terminal before recording the first episode and do **not** pass
`--hand-sdk` to `start_capture_session.sh`; that option intentionally starts a
second, disarmed SDK owner for observation only.

In that controller window, `f` advances the configured cycle and `q` exits the
controller only. The supplied right-hand cycle is loaded from
`gestures/o6_tuned.json`: gesture `0` (open mapping), then gestures `1`,
`2`, and `3` (grasp mappings), and back to `0`. Edit the `gripper_state`
mapping in `config/hand_presets.json` only after a dry run and supervised
hardware check. The controller continuously publishes
`/teleop/right/gripper_state` as `std_msgs/msg/UInt8` (`0=open`, `1=closed`),
and the recorder includes this topic in every new bag. The direct O6 backend
uses normalized `[0,100]` positions and converts them to raw CAN internally;
the ROS command evidence remains in the project `[0,255]` contract. Canonical
model inputs use only the binary projection. No binary state is claimed before
the first `f` command, which
avoids labeling an unverified initial pose. The current arm trajectory filter
still predicts arm residuals only; the recorded binary stream is ready for a
future gripper/release head and does not silently turn hand state into arm
action supervision.

```bash
bash scripts/start_capture_session.sh \
  --real --physical-estop-ready --confirm=I_UNDERSTAND_REAL_ROBOT \
  --arms=right --manual-segments --episodes=0 \
  --camera-serial <primary_serial> \
  --second-camera-serial <secondary_serial> \
  --second-camera-namespace /camera2/camera \
  --task-id precision_alignment --operator-id operator_01
```

When a display is available, the session opens one persistent `rqt_image_view`
window per configured RGB camera (`/camera/camera/...` and
`/camera2/camera/...`). They run as tmux windows and are closed automatically by
`scripts/stop_capture_session.sh`; they never consume the recorder keyboard.

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

For tactile-enabled hardware capture, opt in to the LinkerHand SDK while
keeping hand actuation disarmed:

```bash
bash scripts/start_capture_session.sh --hand-sdk --left-touch --right-touch
```

To start and record a second RealSense, provide its physical serial. The
launcher verifies both devices, waits for both RGB-D topic pairs, and passes
their namespaces to the recorder:

```bash
bash scripts/start_capture_session.sh \
  --second-camera-serial <serial> \
  --second-camera-namespace /camera2/camera
```

For an already-running camera node, pass all camera roots directly to the
recorder, comma separated:

```bash
CAMERA_NAMESPACES=/camera/camera,/camera2/camera \
bash scripts/record_episode.sh
```

The recorder always captures the driver-accepted `vendor_command` and measured
joint state. It also subscribes to TCP pose, task-context/event, and tactile
topics when publishers are present. TCP pose and its calibration are optional:
they are neither required to collect an episode nor required for the ACT
projection or `A_action` admission. `vendor_command` is evidence of the command
accepted for SDK transmission; it is not an observed robot action.

Before a real armed capture, `start_capture_session.sh` runs the strict
read-only sample preflight. It requires a message from raw/filter/projected
commands, driver command, and measured joint state for both arms. Run it
directly for diagnosis:

```bash
python3 scripts/preflight.py --mode capture --source real --sample-timeout-s 5
```

Add `--require-tactile` only when both tactile SDK streams were explicitly
enabled. The check never publishes a command or invokes hardware SDK APIs.

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
frame references when their source topics exist. Real records also include the
latest force/matrix/mass tactile sample when it is fresh enough. A missing
source topic is listed in the export manifest; no absent signal is synthesized.

## Canonical v0.1 And ACT Projection

Materialize each derived arm JSONL into the source-agnostic canonical record:

```bash
/usr/bin/python3 tools/exported_jsonl_to_canonical_episode.py \
  --export-jsonl <derived>/right_episode.jsonl \
  --output-dir <derived>/canonical-right \
  --source real --task-id usb_c_insertion \
  --configuration-id changing_layout
```

This writes control, commands, optional task-context, events, tactile, and
camera-reference streams plus `episode.manifest.json`. It defaults to
`audit_only/A_audit`. `A_action/filter_training` is allowed when raw/filter/
projected/controller commands, measured state, synchronization, and explicit
terminal audit are complete. Geometry context, TCP, external-camera calibration,
insertion depth, tactile, and derived observed action are optional. No command
is promoted to observed state.

Create the required explicit terminal audit immediately after each episode:

```bash
python3 tools/finalize_episode_audit.py \
  --output <derived>/terminal_audit.json --episode-id <episode_id> \
  --success --termination-reason operator_verified \
  --operator-id operator_01 --evidence-ref <run>/artifacts/rosbag2
```

Use `--failure` for unsuccessful trials and add `--safety-violation` or
`--unlogged-external-override` whenever applicable. The tool refuses to
overwrite an existing audit.

The ACT adapter is a documented projection rather than a second source of
truth. It requires `policy_training` admission and actual extracted image files
referenced by the canonical camera stream:

```bash
/usr/bin/python3 tools/extract_rosbag_images.py \
  --bag <run>/artifacts/rosbag2 --topic /camera/camera/color/image_raw \
  --output-dir <derived>/frames --camera-id rgb

python3 tools/canonical_episode_to_act_dataset.py \
  --manifest <derived>/canonical-right/episode.manifest.json \
  --output-dir <dataset>/episode_000000 --camera-id rgb \
  --camera-index <derived>/frames/rgb_frames.jsonl
```

It emits `observation.images.*`, `observation.state`, `action`, boundaries and
split metadata. Image normalization and the exact installed LeRobot schema are
recorded at training time, rather than silently inferred by the capture adapter.

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

For the first automatic audit experiment, download the frozen Qwen visual
auditor to the mounted mobile SSD (the script detects `/media/$USER/Cyan_data`):

```bash
bash scripts/download_qwen_auditor.sh
```

The model is `Qwen/Qwen2.5-VL-3B-Instruct` at an immutable revision. The first
experiment keeps it frozen and uses it only for offline, low-frequency JSON
pre-labels; no Qwen process is started by the recorder and no model output can
enter a robot command path.

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
