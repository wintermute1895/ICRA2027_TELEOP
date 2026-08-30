# Simulation command mirror

`sim_robot_driver` is the simulation-side endpoint of the shared command path.
It does not contain a second joint mapping, filter, or safety policy.

```text
LinkerTA/keyboard → teleop_control_bridge → validated FollowJoint
                                             ├─ lbot_driver → official SDK → robot
                                             └─ sim_robot_driver → MuJoCo → /sim/robot1 state
```

The default simulation launch never starts `lbot_driver` and cannot send a
robot command. `follow_joint` mode consumes the exact payload that the real
driver would receive. `vendor_command` mode consumes the explicit command
event published by `lbot_driver` immediately before its SDK call, for shadow
comparison.

## Hand command parity

The official L10 and O6 ROS2 SDK nodes consume `sensor_msgs/msg/JointState`
positions in the range `[0, 255]` on:

```text
/robot1/left_hand/control_cmd
/robot1/right_hand/control_cmd
```

The simulation mirror subscribes to these same topics. Select the installed
pair with `left_hand_model:=L10 right_hand_model:=L10` or
`left_hand_model:=O6 right_hand_model:=O6`; L10 expects ten positions and O6
expects six. The independent left/right parameters remain available only for
diagnostics. It publishes the command-domain state below
`/sim/robot1` and the corresponding MuJoCo primary-joint state in radians:

```text
/sim/robot1/left_hand/joint_states
/sim/robot1/right_hand/joint_states
/sim/robot1/left_hand/model_joint_states
/sim/robot1/right_hand/model_joint_states
```

Example, simulation only:

```bash
ros2 launch sim_robot_driver sim_teleop.launch.py \
  model_path:=$PWD/assets/robots/linker_platform/sensorized/a7_l10_usb_c_insertion.mjcf.xml \
  render:=true keyboard:=false left_hand_model:=L10 right_hand_model:=L10
ros2 topic pub --once /robot1/left_hand/control_cmd sensor_msgs/msg/JointState \
  "{position: [255.0, 128.0, 200.0, 180.0, 160.0, 140.0, 120.0, 100.0, 80.0, 60.0]}"
```

The visual model contains twenty articulated hand joints while L10/O6 expose
ten/six SDK channels. The simulation maps the official primary-channel order
and couples distal flexion for visualization. This coupling must be calibrated
against hardware before using hand pose error as a quantitative metric.

For real hardware, launch `hand_interface.launch.py` for the installed L10 or
O6 pair and `launch_sdk:=true`; it routes the same command topics through the
official SDK and CAN. Never run that launch with `armed:=true` during a
simulation-only test.

The MuJoCo model is optional at runtime. The obsolete O2-derived sensorized
model was removed because its shoulder mount was at `z=0`; until the corrected
shoulder-mounted model is imported, run without `model_path`. Without `model_path`, the node still
publishes simulation joint states for headless pipeline tests. The launch file
uses `/home/ilex/miniforge3/envs/mpc_env/bin/python` by default: it is Python
3.10 and has both ROS2 `rclpy` and MuJoCo 3.8.0. Override `mujoco_python:=...`
only with another Python 3.10 ROS2-compatible environment.

## Simulation-only keyboard test

```bash
cd "$(git rev-parse --show-toplevel)"
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash

ros2 launch sim_robot_driver sim_teleop.launch.py \
  render:=false
```

The keyboard terminal uses `1..7` to select a joint, `a/d` to decrement or
increment it, Tab to switch arms, `r` to reset the selected arm, and `q` to
quit. The source values are degrees because that is the LinkerTA input
contract; the bridge converts to radians and applies the existing verified
mapping/filter/safety configuration. `Space` toggles the active simulated hand
between `open` and `power_grasp`; `o` selects open and `g` selects grasp. Hand
commands use the official SDK's `[0,255]` domain on the shared hand topics.

For a headless command-path test:

```bash
ros2 launch sim_robot_driver sim_teleop.launch.py render:=false
ros2 topic echo /sim/robot1/left_arm/joint_states --once
```

## Shadow mode

Start the normal hardware launch with the operator-controlled `armed` policy,
then start only the mirror with:

```bash
ros2 run sim_robot_driver mujoco_command_mirror --ros-args \
  -p input_mode:=vendor_command \
  -p command_namespace:=/robot1
```

Simulation state is intentionally published below `/sim/robot1`; hardware
state remains below `/robot1`. This prevents accidental topic collisions.

## Causal Command Filter v0

`causal_filter_node` is a simulation-only experiment adapter. It reads the
bridge's already mapped command and simulation joint state, predicts a
successful-trajectory action prior from causal history, then emits a bounded
blend on `/filter_v0/<arm>_arm/joint_follow`. Missing state, model mismatch,
or an out-of-distribution feature vector falls back to the mapped command.
It never starts a hardware driver and is not part of the hardware launch.

Train only from an explicitly admitted `teleop_episode/v0.1` projection.
The rosbag exporter produces derived `episode/v1` rows and is not sufficient for
this claim. A legacy derived row may be used only for an engineering smoke test,
never for `A_action` or a reported flywheel result:

```bash
python3 tools/canonical_episode_to_filter_jsonl.py \
  --manifest evidence/sim/<episode>/episode.manifest.json \
  --control-jsonl evidence/sim/<episode>/streams/control.jsonl \
  --commands-jsonl evidence/sim/<episode>/streams/commands.jsonl \
  --task-context-jsonl evidence/sim/<episode>/streams/task_context.jsonl \
  --output derived/filter_training.jsonl
```

The adapter enforces successful `A_action` admission, synchronization validity,
and the complete `raw -> filter -> projected -> executed` causal chain before
training can consume the output.

Launch it in the simulation path only:

```bash
ros2 launch sim_robot_driver sim_teleop.launch.py render:=false \
  filter_enabled:=true filter_model_path:=/absolute/path/filter.json
```

With `filter_enabled:=true`, the ordinary bridge is deliberately unarmed and
the mirror consumes only `/filter_v0`; this prevents competing command
