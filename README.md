# Robot teleoperation platform

面向双臂机器人遥操、多模态数据采集和离线轨迹评估的 ROS2 平台。任务和论文名称不
写入软件架构；不同实验通过 `config/experiments/` profile 扩展。

主链路为：

```text
LinkerTA → ROS2 关节状态 → 滤波/方向映射 → 安全桥接 → LK73
                         ↓
              RGB-D、关节、TF、时间戳
                         ↓
              rosbag2 + RunEvidence episode
```

本项目负责设备适配、遥操映射、安全机制、相机采集、时间同步和 episode 记录。
DexCatch 是独立的抓取/规划项目；这里只在离线阶段调用它评估 FK/IK、限位、奇异性、
碰撞和轨迹质量，不把它接入实时控制闭环，也不修改它的项目叙事。

架构见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，A/B 设计和评分见
[docs/EXPERIMENT_AND_SCORING.md](docs/EXPERIMENT_AND_SCORING.md)，操作入口见
[TELEOP_QUICKSTART.md](TELEOP_QUICKSTART.md)。

```bash
./scripts/build_ros2_workspace.sh
bash scripts/install_lerobot.sh
bash scripts/start_capture_session.sh --config=config/capture_session.env
```

## Data conversion

The rosbag2 run is the immutable capture record. Canonical data is the stable
audit/interchange layer, while LeRobot is a replaceable training projection.
One production command performs all projections and writes an official local
LeRobot v3 dataset without changing the source run:

```bash
bash scripts/convert_episode_to_lerobot.sh \
  --run-dir evidence/teleop/<completed-episode> \
  --camera main_rgb=/camera/camera/color/image_raw \
  --camera auxiliary_rgb=/camera2/camera/color/image_raw
```

The real terminal audit must admit the episode for `policy_training`. For a
conversion-only smoke test that never changes the real audit:

```bash
bash scripts/test_rosbag_to_lerobot.sh evidence/teleop/<completed-episode>
```

When the same canonical episode also passes the stricter `A_action` causal gate,
the production command additionally writes `filter/filter_training.jsonl`.
Internal stream paths are resolved from the manifest and remain portable when
the complete derived directory is moved.

Task-aware filter training adds a frozen VLM view before CVAE training. Generate
embeddings with the selected VLM implementation, then attach them by timestamp:

```bash
VLM_CACHE_DIR=<vlm-cache> bash scripts/prepare_vlm_filter_view.sh \
  --episode filter/filter_training.jsonl \
  --camera main_rgb=derived/frames/main_rgb_frames.jsonl \
  --camera auxiliary_rgb=derived/frames/auxiliary_rgb_frames.jsonl \
  --output-dir derived/vlm-filter-view
```

An optional local VLM generator is included for a reproducible baseline:
provision a local environment and cache the selected weights with
`bash scripts/install_vlm.sh --download`, then run
`tools/encode_images_with_vlm.py` on an image-index JSONL and attach its output.
The encoder loads the model once and supports multiple named camera indexes in
one pass; relative frame references are resolved relative to each index file.
After the first successful download, add `--local-files-only` to guarantee that
an experiment does not silently access the network.
The script reuses `teleop-train` by default so CUDA/PyTorch is not duplicated;
pass `--env-name teleop-vlm` when strict environment isolation is required.
The default task-aware model is SigLIP2; CLIP remains a baseline. The VLM is
frozen during filter training; changing the VLM requires a new embedding
manifest and experiment revision.

Use `config/filters/trajectory_cvae_transformer_v0_2_vlm.yaml` for the
task-aware model; its `visual_dim: 1536` is two concatenated 768-dimensional
SigLIP2-base camera embeddings. For another VLM or camera count, set
`model.visual_dim` to the resulting width in a new versioned config. The
attachment manifest records model identity, source hashes, camera and alignment;
partial embedding coverage is rejected.

## Learned filter

The paper-model implementation is simulator-independent and lives in
`src/teleop_filter/`. Its first version is a conditional trajectory VAE with a
Transformer history encoder, learned conditional prior, training-only
posterior, KL regularization, and bounded residual composition. It is currently
authorized only for offline evaluation and simulation.

```bash
PYTHONPATH=src conda run -n teleop-train python \
  tools/train_trajectory_filter.py \
  --episode derived/filter_training_001.jsonl \
  --episode derived/filter_training_002.jsonl \
  --output-dir runs/filter/trajectory_cvae_v0_1

PYTHONPATH=src conda run -n teleop-train python \
  tools/evaluate_trajectory_filter.py \
  --checkpoint runs/filter/trajectory_cvae_v0_1/trajectory_filter.pt \
  --episode derived/filter_validation_001.jsonl \
  --output-dir runs/filter/trajectory_cvae_v0_1/evaluation_001
```

The filter trainer requires an explicit `expert_action_target_rad` field from a
verified correction segment. At runtime the predicted expert action is compared
with the current raw teleoperation command to form a bounded residual. The
legacy `residual_target_rad` field is accepted only for explicitly enabled
`synthetic_smoke_only` regression fixtures and is never inferred as
`controller_command - raw_command`.

训练和评估只接受明确准入的 filter-training JSONL。推理输出经过有界残差组合，当前仍
只允许离线与仿真使用，不能直接发布到真实机器人控制话题。

## Standalone USB-C insertion scene

The connector-insertion asset layer is independent of ROS2, teleoperation,
planning, DexCatch, hardware, and recording. It uses parameterized MuJoCo
primitives as a mandatory physics baseline; optional visual meshes are
visual-only and must carry a source/license manifest.

```bash
cd "$(git rev-parse --show-toplevel)"
python -B \
  tools/build_connector_insertion_scene.py \
  --task usb_c_laptop_insertion \
  --output /tmp/usb_c_laptop_insertion.mjcf.xml

python -B \
  tools/validate_connector_insertion_scene.py \
  --scene /tmp/usb_c_laptop_insertion.mjcf.xml --require-named-contract

python -B \
  tools/validate_connector_insertion_scene.py \
  --scene /tmp/usb_c_laptop_insertion.mjcf.xml --check-collisions

python -B \
  tools/validate_connector_insertion_scene.py \
  --scene /tmp/usb_c_laptop_insertion.mjcf.xml --check-success-geometry

MUJOCO_GL=egl python -B \
  tools/validate_connector_insertion_scene.py \
  --scene /tmp/usb_c_laptop_insertion.mjcf.xml \
  --render /tmp/usb_c_contact_sheet.png
```
