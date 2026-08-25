# L10 Hand Gesture Tool — Delivery Package

This folder is self-contained: extract it anywhere, open a terminal **inside this folder**, then run the commands below. It includes the L10 CAN SDK, the recorded gestures `0`, `1`, and `2`, a visual player, and a gesture recorder.

## Before use

1. Connect the USB-CAN device and power the L10 hand.
2. In a terminal, bring up the CAN interface at 1 Mbit/s:

```bash
sudo ip link set can0 down
sudo ip link set can0 up type can bitrate 1000000
cat /sys/class/net/can0/operstate
```

The last command must print `up`. Only one program may use `can0` at a time.

Required Python packages for the direct hand tools: `python-can`, `numpy`, `pydantic`, and `pyyaml`; on Ubuntu, also install `python3-tk` for the GUI if it is missing. ROS2 tools additionally require a sourced ROS2 environment with `rclpy` and `std_msgs`.

```bash
pip install python-can numpy pydantic pyyaml
sudo apt install python3-tk
```

## Execute the delivered gestures 0 / 1 / 2

```bash
python hand_gesture_player.py --hand L10 --side right --can can0 --output gestures
```

The visual window displays all 10 values of the selected gesture.

- Click the window to focus it.
- Press `0`, `1`, or `2` to choose a gesture. Choosing does **not** move the hand.
- Press `Enter` (or click **Execute current gesture**) to send all 10 joints together.
- Press `Esc` to exit.

The gestures are in `gestures/l10_gestures.py` and `gestures/l10_gestures.json`.

## Use the O6 right hand (0 / 1 / 2)

O6 is exposed by `lbot_driver` as a six-joint hand, so its ROS topics use the
`set_l6_*` suffix. The packaged poses are in `gestures/o6_gestures.py` and
`gestures/o6_gestures.json`:

```bash
source ../scripts/d0_env.sh
./run_ros_publisher_o6_right.sh
```

The publisher sends six `UInt8` values continuously to
`/robot1/right_hand/set_l6_joint` and initializes the matching speed/force
topics. Enter `0`, `1`, or `2` followed by Enter to select a pose; enter `q`
to stop. For real O6 control plus rosbag capture, use the GUI mirror:

```bash
./run_ros_gui_o6_right.sh
```

It drives O6 directly through `can0` and continuously mirrors the active pose
to `/robot1/right_hand/set_l6_joint` as six raw `0..255` bytes.

The O6 Python SDK is bundled at
`thrid_party/linkerbot-python-sdk-main/src/linkerbot/hand/o6` and is loaded by
the recorder automatically. SDK angles use `0..100`; the ROS publisher converts
them to the driver's raw `0..255` bytes. To re-record the three slots directly
from the right O6 on `can0`, keep the hand clear and run:

```bash
./run_recorder_o6_right.sh
```

Adjust with the arrow keys, press `s` to overwrite slots `0`, `1`, and `2` in
order, then press `q` to write both gesture files. Press `r` to refresh the
actual hand state before editing. O6 is otherwise published through
`lbot_driver`; `--direct-can` is supported only for L10 in this package.

## Publish hand data for the camera + arm rosbag

`run_ros_gui_o6_right.sh` is the recording path: it opens `can0` for direct O6
control and mirrors the active six-joint pose to ROS continuously. The
`tmux_d0.sh` hand window starts this script automatically. Do not run it
together with another O6 publisher or CAN driver for the same hand.

完整的“相机 + 机械臂 + 手”录包与分流流程（`d0_record.py` / `d0_split.py` /
`tmux_d0.sh`）见 `../scripts/README.md`。

## Adjust or record a new gesture

```bash
python -m hand_gesture_recorder.recorder --hand L10 --side right --can can0 --output gestures --step 1
```

- `1`–`9`: move the cursor to joint 1–9; `0`: joint 10.
- `Space`: add/remove the cursor joint from multi-select.
- `a`: select all; `x`: clear multi-select.
- Arrow keys: adjust selected joints together (up/right increases; down/left decreases).
- `r`: refresh the actual reported hand state.
- `s`: save. Existing 0/1/2 are retained; the next save becomes 3.
- `q`: exit and write the gesture files.

## Important safety notes

The recorded poses can move the real hand. Keep fingers and objects clear before pressing Enter. Do not run this together with a ROS2 hand driver or another CAN program, because they will compete for `can0`.

## Offline UI check

Without hardware, test the UI only:

```bash
python hand_gesture_player.py --hand L10 --simulate --output gestures
python hand_gesture_player.py --hand O6 --simulate --output gestures
```
