# LinkerHand integration

The installed O6 active-control path is intentionally separate: it uses the
repository `linkerbot` O6 backend through `scripts/start_hand_control_session.sh`
because the official ROS SDK did not recognize that hand's firmware. That
single process owns CAN and publishes the same project command/state evidence
topics. Do not run it together with the official SDK path documented below.

The upstream SDK is pinned in `third_party/linkerhand_ros2_sdk` as a Git
submodule. Its source is not modified. The ROS2 workspace exposes it through
the read-only link `ros2_ws/src/linker_hand_ros2_sdk`.

Our `hand_adapter` exposes:

```text
/robot1/left_hand/control_cmd   sensor_msgs/JointState, O6: 6 values
/robot1/right_hand/control_cmd  sensor_msgs/JointState, L20 Lite: 10 values
/robot1/left_hand/joint_states
/robot1/right_hand/joint_states
```

The adapter translates commands to the official SDK topics
`/cb_left_hand_control_cmd` and `/cb_right_hand_control_cmd`. Commands are
native hand positions in `[0,255]`, not arm radians. It defaults to
`armed=false` and never opens CAN.

The official SDK is started only with explicit `launch_sdk:=true`. L20 Lite is
treated as the current product name for L10, so the adapter uses 10 positions
and the upstream SDK receives `L10`. Firmware and joint-order confirmation is
still required before any real command. The launch deliberately separates
`right_model:=L20Lite` from `right_sdk_model:=L10`.

Build and safe interface-only launch:

```bash
cd "$(git rev-parse --show-toplevel)"
git submodule update --init --recursive
source /opt/ros/humble/setup.bash
./scripts/build_ros2_workspace.sh
source ros2_ws/install/setup.bash
ros2 launch hand_adapter hand_interface.launch.py launch_sdk:=false armed:=false
```

Real CAN launch is deliberately not documented as an unconditional command.
Before enabling it, confirm the two CAN interfaces, hand model, firmware,
joint order, and emergency-stop readiness.
