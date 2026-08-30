# Hand Simulation and Real Command Contract

The hand command interface is deliberately shared between simulation and real
hardware. The backend changes; the publisher does not.

## Topics and Units

```text
/robot1/left_hand/control_cmd    sensor_msgs/msg/JointState
/robot1/right_hand/control_cmd   sensor_msgs/msg/JointState
```

`JointState.position` contains unsigned-like actuator positions represented as
floating-point values in `[0,255]`, matching the official LinkerHand ROS2 SDK.
They are not radians. The simulation-only `model_joint_states` topic reports
MuJoCo joint angles in radians.

Official channel order:

```text
L10: thumb_cmc_pitch, thumb_cmc_yaw, index_mcp_pitch,
     middle_mcp_pitch, ring_mcp_pitch, pinky_mcp_pitch,
     index_mcp_roll, ring_mcp_roll, pinky_mcp_roll, thumb_cmc_roll

O6:  thumb_cmc_pitch, thumb_cmc_yaw, index_mcp_pitch,
     middle_mcp_pitch, ring_mcp_pitch, pinky_mcp_pitch
```

## Backends

```text
sim:
  shared command topic -> sim_robot_driver -> MuJoCo

real:
  shared command topic -> hand_adapter -> official linker_hand_ros2_sdk -> CAN
```

The simulation node never imports or opens the CAN SDK. The real backend must
be explicitly armed and physically checked before motion is allowed.

## Switching

Start simulation with the installed hand pair. For L10:

```bash
ros2 launch sim_robot_driver sim_teleop.launch.py \
  model_path:=$PWD/assets/robots/linker_platform/sensorized/a7_l10_usb_c_insertion.mjcf.xml \
  left_hand_model:=L10 right_hand_model:=L10
```

For O6, replace both model parameters with `O6`.

Start real hardware separately with the installed pair. For L10:

```bash
ros2 launch hand_adapter hand_interface.launch.py \
  left_model:=L10 right_model:=L10 \
  left_sdk_model:=L10 right_sdk_model:=L10 \
  launch_sdk:=true armed:=false
```

For the O6 pair, replace all four model arguments with `O6`. The independent
left/right options are retained for diagnostic use; they are not a statement
that the deployed platform has one L10 and one O6.

Only after the SDK connection, CAN interface, hand state, emergency stop, and
first-command checks pass should `armed` be enabled. Running both backends
with the same command topic is a deliberate shadow configuration: simulation
will mirror the command while the real backend remains `armed:=false` until
the operator explicitly approves it.

The current MuJoCo asset is an L10 visual hand on both arms. O6 commands are
supported at the semantic topic level and drive the six corresponding primary
visual joints; the remaining L10 visual joints stay coupled/neutral. An
O6-specific visual asset can replace this mapping without changing the ROS2
command contract.
