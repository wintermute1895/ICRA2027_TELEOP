# MuJoCo Hand And Camera Calibration

This procedure edits only the MuJoCo/URDF assets. It never starts ROS2, CAN, the robot driver, or physical hardware.

## Start

From an SSH terminal on `ilex22`, with the local GNOME desktop logged in and unlocked:

```bash
cd /mnt/F/ICRA2027_TELEOP
bash scripts/launch_local_mujoco_calibration.sh
```

The window opens on `ilex22`'s own desktop. Inspect and operate it through the existing remote desktop session. The launcher discovers the local `DISPLAY` and `XAUTHORITY`; do not use X11 forwarding.

## Controls

Click the MuJoCo window first so it receives keys.

| Key | Select |
| --- | --- |
| `0` | Whole robot in the world |
| `1` | Head D435i camera |
| `2` | Left wrist D405 camera |
| `3` | Right wrist D405 camera |
| `4` | Left hand mounting transform |
| `5` | Right hand mounting transform |

| Key | Action |
| --- | --- |
| `W` / `S` | Local/world X plus/minus |
| `A` / `D` | Local/world Y plus/minus |
| `R` / `F` | Local/world Z plus/minus |
| `I` / `K` | Roll plus/minus |
| `J` / `L` | Pitch plus/minus |
| `U` / `O` | Yaw plus/minus |
| `[` / `]` | Halve/double translation and rotation increment |
| `P` | Save calibration |
| `Esc` | Close viewer |

The robot world transform uses world axes. Hand and camera transforms are relative to their parent wrist/body frames. Start at the default 1 cm and 2 degree increments; use `[` before fine alignment.

## Save And Reuse

Press `P`. The output is:

```text
config/sim/mujoco_sensor_calibration.json
```

It contains `robot_world`, `hand_mounts.left/right`, and the three camera poses. The launcher loads it automatically on the next run.

To bake the saved hand and camera setup into the generated assets:

```bash
python -B tools/generate_a7_sensorized_urdf.py \
  --calibration config/sim/mujoco_sensor_calibration.json

python -B tools/generate_a7_sensorized_mjcf.py \
  --calibration config/sim/mujoco_sensor_calibration.json
```

The first command applies the hand-mount deltas to the fixed wrist-to-hand joints. The second applies the saved D435i/D405 camera poses. Keep the calibration JSON under version control along with the generated URDF/MJCF.

## Acceptance

Before using a calibrated model for synthetic data, confirm all of the following in MuJoCo:

1. The wrist mechanical interface does not intersect the hand base through its intended joint range.
2. Both hand palms have the expected mirror symmetry at the zero arm pose.
3. The head view contains both hands and the task surface.
4. Each wrist view contains its own fingertips and the intended contact area, without the robot body blocking most pixels.
5. Reloading the saved JSON reproduces the scene exactly.

## Current Calibrated Installation

The current saved calibration is:

- robot world offset: approximately `[0.25, -0.08, -0.80]` m;
- left and right hand mounts: symmetric approximately `[-0.02, 0, -0.06]` m;
- left and right hand mount rotations: mirrored yaw offsets;
- head D435i and both wrist D405 poses are stored in the JSON.

The calibration file was checked for finite camera quaternions. If a future save produces `NaN`, do not use it for asset generation; restore the last valid JSON first.

## Build The Task Table Scene

Once the robot and hand installation are accepted, create the first precision-assembly scene:

```bash
python -B tools/build_a7_task_scene.py
```

Output:

```text
assets/robots/linker_platform/sensorized/a7_l10_task_scene.mjcf.xml
```

The scene adds a small table in front of the robot and three fixed diagnostic objects: a cube, cylinder, and sphere. They are collision-enabled and deliberately simple for initial reachability, camera framing, and grasp-pose data collection. The robot/hand/camera calibration remains in the JSON and is not silently changed by scene creation.

## Interactive Task Scene Editing

The table and task objects have a separate, reusable layout file:

```text
config/sim/a7_task_scene_layout.json
```

Start the local MuJoCo editor and an SSH-visible status terminal:

```bash
bash scripts/start_a7_scene_editor_tmux.sh
tmux attach -t a7_scene_editor
```

The scene editor uses grouped selection, so adding objects does not consume a global sequence of direct-selection keys:

1. Press `G`.
2. Press `1` for `scene` or `2` for `objects`.
3. Press `0` through `9` to select the item in that group.
4. Use `WASD/RF` to translate and `IJKLUO` to rotate.
5. Press `P` to save the layout JSON.

The tmux `status` window shows the active group, selected object, and every move/rotation. Rebuild the task scene after a saved layout with `python -B tools/build_a7_task_scene.py`.
