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

日常数采的相机、会话、操作者和默认任务参数均在
`config/capture_session.env`；真机急停与授权仍必须显式写在命令行：

```bash
bash scripts/stop_capture_session.sh
bash scripts/start_capture_session.sh \
  --real --physical-estop-ready --confirm=I_UNDERSTAND_REAL_ROBOT
```

## Data conversion

本项目的 raw evidence、派生数据和训练输出可迁移到外置盘。先运行
`skills/external-disk-rw/scripts/mount_cyan_data_rw.sh`，再执行：

```bash
bash scripts/migrate_project_data_to_external.sh
```

脚本默认只复制并校验 `evidence/`，确认无误后如需删除本地副本再显式添加
`--delete-source`。源码、Git、第三方 SDK、虚拟环境和模型权重不会迁移。

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

触觉不是当前主数采或滤波器训练输入。仓库中保留的 tactile/hand SDK topic 仅用于
历史硬件适配和明确 opt-in 的诊断；默认 `config/capture_session.env` 不启动它们，
不能据此认为当前数据包含可用触觉监督。

When the same canonical episode also passes the stricter `A_action` causal gate,
the production command additionally writes `filter/filter_training.jsonl`.
Internal stream paths are resolved from the manifest and remain portable when
the complete derived directory is moved.

Task-aware filter training adds a frozen VLM view before CVAE training. Generate
embeddings with the selected VLM implementation, then attach them by timestamp:

```bash
bash scripts/prepare_filter_training_view.sh \
  --config=config/pipeline/filter_training_view.yaml
```

编辑 `config/pipeline/filter_training_view.yaml` 中的 episode/projection 路径即可；
其中相机顺序、SigLIP2 revision、移动硬盘 cache、device、batch size 和时间对齐阈值
都会写入运行 manifest。旧的逐项参数入口仍保留用于兼容脚本。

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

推荐使用 round 配置作为唯一训练入口：

```bash
bash scripts/start_filter_training.sh \
  config/filters/coldstart_episode1_vlm_v1.yaml
```

该入口会先确认 `/media/ilex/Cyan_data` 确实挂载为可写的外置盘，再启动
`teleop-train` GPU 环境；外置盘丢失或只读时会在训练前停止。

训练完成后可在本机启动只读可视化页面：

```bash
python tools/serve_filter_dashboard.py \
  --round runs/filter/round_001
# 浏览器打开 http://127.0.0.1:8765/
```

该页面只读取 `training_report.json`、`evaluation_report.json` 和
`predictions.jsonl`，不连接 ROS、不发布控制命令。底层脚本仍保留用于单元测试和
调试，但正式实验应记录 `round_manifest.json`。

The paper-model implementation is simulator-independent and lives in
`src/teleop_filter/`. Its first version is a conditional trajectory VAE with a
Transformer history encoder, learned conditional prior, training-only
posterior, correction gate, KL regularization, nominal zero-residual regularization,
and bounded residual composition. Residual composition is only the deployment
mechanism; the model is trained on nominal and corrective expert-action windows.
It is currently
authorized only for offline evaluation and simulation. An independent ROS2
adapter is available for shadow/runtime integration between LinkerTA and the
bridge. It is disabled by default and requires a pinned checkpoint, shadow
validation, bounded correction, safety projection, and explicit approval.

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

To materialize the correction-aware action view before VLM attachment, use the
explicit segment adapter (the action field must be chosen from the recorded
episode contract):

```bash
python tools/build_correction_segment_view.py \
  --episode canonical/filter_training.jsonl \
  --events artifacts/audit_events.jsonl \
  --expert-action-field master_joint_raw \
  --output derived/correction_view.jsonl
```

训练和评估只接受明确准入的 filter-training JSONL。推理输出经过有界残差组合；真机部署
必须经过 runtime 配置中的 checkpoint/hash 晋级，并且只能通过 supervisor -> bridge 边界发布。

## ACT / filter deployment

ACT 和 learned filter 都只能发布 candidate。统一监督层
`tools/model_deployment_supervisor.py` 负责 shadow/active 选择、超时、维度、
NaN、幅度和步长检查；bridge 只订阅 `/model_deployment/right_arm_joint_control`，
继续负责单位映射、One-Euro、限位、首次 MoveJ 和 armed gate。默认配置是 shadow：

```bash
bash scripts/start_model_deployment.sh config/runtime/model_deployment.yaml --shadow
```

ACT 的 GPU worker 与 ROS2 adapter 分离，启动方式和 filter 相同，详见
`docs/engineering/MODEL_DEPLOYMENT.md`。当前没有任何模型被声明为真机安全可用；
active 之前必须完成 held-out 评估、shadow 运行和人工安全确认。

完整 rollout（录制、部署、评测）使用统一入口：

```bash
bash scripts/start_model_rollout.sh --config config/runtime/rollout.yaml --shadow \
  --record-dir /media/ilex/Cyan_data/ICRA2027_TELEOP_DATA/rollouts/<timestamp>
# Ctrl-C 停止后：
bash scripts/evaluate_model_rollout.sh \
  --bag /media/ilex/Cyan_data/ICRA2027_TELEOP_DATA/rollouts/<timestamp>
```

评测是只读的 rosbag 导出和轨迹质量检查，不会自动把 review 结果当成成功，也不会解除真机 armed gate。

模型生成后可直接晋级为一次性 runtime 配置，不必改共享 YAML：

```bash
bash scripts/promote_model_checkpoint.sh --kind act \
  --checkpoint /path/to/policy --output /media/ilex/Cyan_data/ICRA2027_TELEOP/config/act-promoted.yaml
bash scripts/start_model_rollout.sh --source act \
  --act-config /media/ilex/Cyan_data/ICRA2027_TELEOP/config/act-promoted.yaml --shadow
```

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
