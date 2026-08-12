# Hand Hardware Test

The official LinkerHand ROS2 SDK owns the CAN protocol, motor limits, faults,
speed and force handling. The platform adapter does not replace those controls.
Its only role is a shared topic contract and an `armed` gate.

This procedure is for one installed hand pair at a time: either both L10/L20
Lite hands or both O6 hands. Do not assume mixed left/right hardware.

## 1. Passive CAN Diagnosis

This sends no CAN frame and starts no SDK:

```bash
python3 scripts/preflight.py --mode hand

/usr/bin/python3 tools/diagnose_hand_can.py \
  --interface can0 --interface can1 \
  --listen-s 5 \
  --output /tmp/hand_can_diagnostic.json
```

Confirm that the intended interface exists, is `UP`, and reports `CAN` details.
`candump` is passive; install `can-utils` if it is unavailable.

## 2. Explicit CAN Enable

If an interface is down, enable only that Linux SocketCAN interface. This does
not start the SDK or move a hand:

```bash
bash scripts/enable_hand_can.sh \
  --interface can0 \
  --bitrate 1000000 \
  --confirm ENABLE_HAND_CAN_INTERFACE
```

The official SDK expects SocketCAN at `1 Mbit/s`. It attempts this setup
internally too, but suppresses setup errors; using the explicit command makes
permission and interface failures visible.

## 3. SDK Observation

Start the official backend through the adapter with `armed:=false`. The SDK
itself may apply its vendor default speed, force, and initial pose during
startup. Keep the hand clear and the physical stop reachable before launch.

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash

ros2 launch hand_adapter hand_interface.launch.py \
  left_model:=L10 right_model:=L10 \
  left_sdk_model:=L10 right_sdk_model:=L10 \
  left_can:=can0 right_can:=can1 \
  launch_sdk:=true armed:=false
```

Use `O6` for all four model arguments when testing the O6 pair. Verify
`/robot1/left_hand/joint_states` and `/robot1/right_hand/joint_states` publish
the expected six or ten channels before allowing a command.

## 4. One Preset Command

The test command only publishes once to the shared adapter topic. It does not
write CAN directly. It waits for a correctly sized feedback state before any
command, defaults to SDK speed/force `40/255`, and requires an explicit E-stop
confirmation.

First inspect the exact command without moving:

```bash
/usr/bin/python3 tools/test_real_hand_preset.py \
  --arm left --model L10 --preset open
```

After official SDK observation and physical setup are satisfactory, restart the
adapter with `armed:=true`, then perform one command:

```bash
/usr/bin/python3 tools/test_real_hand_preset.py \
  --arm left --model L10 --preset open \
  --physical-estop-ready \
  --confirm EXECUTE_ONE_HAND_PRESET_WITH_ESTOP_READY \
  --execute
```

Repeat with `power_grasp`, then the other arm. Do not use the vendor dual-hand
demos as a first movement test: their current source sends both hands together,
sets speed and force to `250/255`, and repeats ten cycles.

## Evidence

`scripts/record_episode.sh` records hand command and hand feedback topics in
addition to arm state. Keep the CAN diagnostic output, SDK log, model/CAN
assignment, and a short operator note with each first-hardware test.
