# Asset and Collision Scene Goal Handoff

## Goal

Build a reusable MuJoCo asset layer for precision connector insertion without
changing teleoperation, ROS2 arm/hand control, data capture, planning, or
paper-facing code.

The first supported task is a USB-C charging plug inserted into a laptop-side
USB-C receptacle. The design must later support USB-A and RJ45 through the
same task-asset interface.

## Scope

Create or import only these artifacts:

```text
assets/tasks/connector_insertion/
  visual/                 licensed laptop / plug visual meshes
  collision/              simplified collision meshes or primitive specs
  usb_c/                  parameterized plug and receptacle MJCF fragments
  manifests/              source URL, license, dimensions, SHA256

config/sim/tasks/
  usb_c_laptop_insertion.json

tools/
  build_connector_insertion_scene.py
  validate_connector_insertion_scene.py
```

Do not edit `ros2_ws`, `teleop_control_bridge`, `hand_adapter`, recorder
scripts, DexCatch, or existing robot URDF/MJCF generation code. The task scene
must be an additional MJCF built around the existing calibrated robot model.

## Non-Blocking Asset Policy

Use two independent layers:

1. Physics baseline: parameterized MuJoCo primitives. This is mandatory and
   contains no downloaded asset. It must always build and validate.
2. Visual enhancement: optional laptop/charger mesh from a source with a
   documented license. A failed download, incompatible mesh, or unclear
   license must leave the physics baseline runnable.

Do not use high-polygon visual mesh directly as the connector collision body.
The receptacle, plug, laptop shell, and table need explicit simplified
colliders.

## Required Scene Contract

The generated scene shall provide named bodies/geometries:

```text
task_laptop
usb_c_plug
usb_c_receptacle
usb_c_entry_funnel
usb_c_insertion_channel
```

It shall include named sites:

```text
usb_c_grasp_site
usb_c_plug_tip_site
usb_c_receptacle_entry_site
usb_c_receptacle_goal_site
```

The plug must be a free body for future grasp attachment. The receptacle and
laptop must be fixed. The first version treats the cable as visual-only; no
deformable cable simulation is required.

## Acceptance Checks

Each check must be executable without ROS2, a display, GPU, or robot hardware.

1. `baseline-build`

```bash
cd /mnt/F/ICRA2027_TELEOP
/home/ilex/miniforge3/envs/mpc_env/bin/python -B \
  tools/build_connector_insertion_scene.py \
  --task usb_c_laptop_insertion \
  --output /tmp/usb_c_laptop_insertion.mjcf.xml
```

Pass criteria: output exists and `mujoco.MjModel.from_xml_path()` compiles.

2. `named-contract`

```bash
/home/ilex/miniforge3/envs/mpc_env/bin/python -B \
  tools/validate_connector_insertion_scene.py \
  --scene /tmp/usb_c_laptop_insertion.mjcf.xml \
  --require-named-contract
```

Pass criteria: all required bodies, geoms, and sites resolve by name.

3. `collision-contract`

```bash
/home/ilex/miniforge3/envs/mpc_env/bin/python -B \
  tools/validate_connector_insertion_scene.py \
  --scene /tmp/usb_c_laptop_insertion.mjcf.xml \
  --check-collisions
```

Pass criteria:

- plug outside the receptacle has no initial penetration;
- a deliberately offset plug contacts the entry funnel/walls;
- an aligned plug at the goal has no penetration;
- laptop/table and plug/receptacle collision groups are enabled.

4. `success-geometry`

```bash
/home/ilex/miniforge3/envs/mpc_env/bin/python -B \
  tools/validate_connector_insertion_scene.py \
  --scene /tmp/usb_c_laptop_insertion.mjcf.xml \
  --check-success-geometry
```

Pass criteria: the report defines and verifies initial tolerances for lateral
offset, angular error, and insertion depth. Suggested initial values are
`1.5 mm`, `5 deg`, and `>= 6 mm`; report them as task parameters rather than
as real hardware claims.

5. `render`

```bash
MUJOCO_GL=egl /home/ilex/miniforge3/envs/mpc_env/bin/python -B \
  tools/validate_connector_insertion_scene.py \
  --scene /tmp/usb_c_laptop_insertion.mjcf.xml \
  --render /tmp/usb_c_contact_sheet.png
```

Pass criteria: nonblank contact sheet showing global, head, and wrist views.

## Asset Sourcing Rules

For every downloaded mesh, create a manifest entry containing:

```json
{
  "source_url": "...",
  "retrieved_at": "ISO-8601",
  "license": "SPDX or source text",
  "attribution": "...",
  "sha256": "...",
  "scale_to_meters": 1.0,
  "used_for": "visual_only"
}
```

Potential visual sources may be evaluated, but none is pre-approved until its
individual asset license is recorded: Objaverse, Google Scanned Objects,
Sketchfab CC assets, manufacturer CAD, RoboCasa, BEHAVIOR-1K, and ManiSkill.

## Deliverables

1. Parameterized USB-C/laptop baseline scene and task JSON.
2. Validator JSON report for all four non-render checks.
3. One rendered contact sheet.
4. Asset manifest and a short source/license note.
5. A concise README section with the five commands above.

## Explicit Non-Goals

- No real robot connection, CAN access, SDK launch, ROS2 control, or data recording.
- No grasp policy, IK, trajectory planning, or teleoperation changes.
- No claim that the contact model matches physical USB insertion force until it
  is calibrated against hardware measurements.
