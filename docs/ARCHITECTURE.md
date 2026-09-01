# Robot teleoperation platform architecture

本仓库是通用的机器人遥操与多模态数据平台，不绑定论文标题。论文问题、A/B 条件和
任务定义属于 experiment profile；设备、控制和数据契约保持稳定。

```text
experiment/   任务、条件、随机化、指标和数据质量门
capture/      episode 生命周期、rosbag2、RunEvidence、时间同步
control/      单位适配、关节映射、滤波、安全门和硬件命令
devices/      LinkerTA、LK73、RealSense 等 ROS2 adapter
interfaces/   ROS2 messages/services、episode schema 和单位约定
data/         rosbag 读取、canonical 物化、ACT/LeRobot 投影
learning/     与 ROS/仿真器解耦的 learned filter 模型与训练
simulation/   MuJoCo 和未来仿真 adapter；不得反向污染模型核心
evaluation/   只读离线评估；可调用 DexCatch 的运动学与规划能力
```

## 当前代码映射

| 层 | 位置 |
|---|---|
| devices | `ros2_ws/src/linkerta`、`ros2_ws/src/lbot_driver` |
| interfaces | `ros2_ws/src/lbot_arm_interfaces`、`research/ResearchOps/DATA_CONTRACT_V0_1.md` |
| control | `ros2_ws/src/teleop_control_bridge` |
| capture | `scripts/start_capture_session.sh`、`tools/capture_episode.py`；shell 只负责启动与环境编排 |
| data | `tools/export_rosbag_episode.py`、`tools/exported_jsonl_to_canonical_episode.py`、`tools/act_jsonl_to_lerobot.py` |
| learning | `src/teleop_filter`、`tools/train_trajectory_filter.py`、`tools/evaluate_trajectory_filter.py` |
| simulation | `ros2_ws/src/sim_robot_driver`、`scripts/run_mujoco_sim_node.sh` |
| experiment | `config/experiments` |
| evaluation | `tools/evaluate_trajectory_quality.py`、`tools/mine_hard_cases.py`、`tools/build_episode_registry.py`、`tools/aggregate_ab_results.py` 和外部 DexCatch 只读评估入口 |

厂商包保留 `lbot_*`/`linkerta` 名称，因为它们是设备 adapter。平台自己的控制包、
节点、话题、脚本和 schema 使用中性名称，不再使用论文缩写。

## 控制数据流

```text
source JointState
  → source unit conversion
  → joint index mapping
  → One-Euro filter (rad)
  → per-arm direction mapping
  → finite/limit/rate/armed safety gate
  → hardware command or shadow output
```

新增控制算法必须支持 `shadow` 模式。方向映射、单位和限位只能来自显式配置，不得
散落在实验脚本或评估代码中。

## Data ownership and projections

```text
rosbag2 + terminal audit              immutable capture evidence
        |
        v
aligned episode JSONL                 source-specific decoded view
        |
        v
teleop_episode/v0.1 canonical         stable audit and causal contract
        |                    |
        v                    v
official LeRobot v3          filter-training JSONL
ACT/policy training          learned-filter training
```

`scripts/convert_episode_to_lerobot.sh` is the production one-command entry.
`scripts/test_rosbag_to_lerobot.sh` creates a synthetic audit only inside its
isolated smoke output and must not be used to label training data. Canonical is
kept because LeRobot does not represent the full raw/filter/projected/controller
causal chain or terminal safety audit; users do not need to invoke each internal
adapter manually.

`policy_training` and `filter_training` have separate admission gates. ACT needs
aligned image, measured state and action coverage. Filter training additionally
requires the full causal command chain and `A_action` admission.

相机参数是 repeatable mapping；两路相机只有在解码、对齐并同时写入独立的
`observation.images.<camera_id>` feature 后，才算进入 LeRobot projection。原始 rosbag
始终保留全部已录制话题。

## Learned-filter boundary

The former causal command-prior implementation is archived under
`legacy/causal_command_filter_v0/` and is not part of the main ROS package or
flywheel training path.

`src/teleop_filter/trajectory_vae.py` is the algorithm core. It contains no ROS,
hardware, task geometry, or simulator imports. The conditional prior is learned
from past operator commands and measured state. The posterior sees the accepted
future action chunk only during training. KL therefore regularizes two learned
conditional distributions; it is not a hand-authored definition of a good
trajectory or proof of a fixed low-dimensional manifold.

The current learned model is `offline_and_simulation_only`. A future ROS adapter
must run shadow evaluation first, publish diagnostics on separate topics, apply
bounded correction and safety projection, and must never replace the hardware
command topic merely by enabling a config flag.

`src/teleop_filter/runtime.py` 负责版本化 checkpoint 加载、训练集统计归一化、先验推理
和有界残差组合；`tools/evaluate_trajectory_filter.py` 只读生成预测与误差报告。该运行时
不导入 ROS 或具体仿真器，因此 MuJoCo 和未来其他 simulator adapter 共享同一模型语义。

任务飞轮的视觉支路由 `tools/encode_images_with_vlm.py` 和
`tools/attach_vlm_embeddings.py` 固定下来：外部 VLM 对解码图像生成冻结 embedding，
按 ROS 时间戳与 filter-training 行对齐并记录模型 provenance；encoder 一次加载模型即可
处理多路命名相机，attach 可以消费一个合并的 embedding JSONL；
`TrajectoryFilterConfig.visual_dim > 0` 时，Transformer token 同时融合动作、状态和
`vlm_embedding`。VLM 不进入真实机器人实时控制闭环，在线阶段只允许 shadow 记录。
`tools/encode_images_with_vlm.py` 提供通用的 CLIP/SigLIP embedding adapter，默认使用
SigLIP2；VLM 依赖单独列在 `requirements-vlm.txt`，`scripts/install_vlm.sh` 负责本地
Conda 环境和可选权重缓存，避免把具体权重和网络下载强行绑定到 ROS/LeRobot 环境。
`trajectory_cvae_transformer_v0_1.yaml` 保留无视觉 baseline；论文的任务感知主模型使用
`trajectory_cvae_transformer_v0_2_vlm.yaml`，要求每个历史窗口都有完整的冻结 embedding；
当前配置把两台相机的 768 维 SigLIP2 embedding 按固定 camera order 拼接为 1536 维。

任务感知模型优先训练显式 `expert_action_target_rad`：它来自人工确认的 correction
segment 中记录的专家动作。运行时再用预测专家动作减去当前 raw teleoperation command
形成 residual。`residual_target_rad` 仅允许带有 `synthetic_smoke_only` provenance 的
隔离回归 smoke；不得由 `controller_command - raw_command` 自动制造，否则模型只会复制
现有控制链路。

任务、reference、policy、安全和 evaluation profile 由
`tools/resolve_experiment_manifest.py` 解析为不可变 manifest。条件采用
`nominal_reference_v1` 等版本化 ID，论文中的 A/B/B0/B1/B2 只是 profile 的角色
映射。任务以 `ContactRichPrecisionAssemblyTask` 作为有边界的基类，而 USB-C 是
连接器插接子类的具体场景；详见 `docs/EXPERIMENT_MANIFESTS.md`。

## DexCatch 边界

DexCatch 是独立抓取项目。本仓库只把已录制 episode 交给它做 FK/IK、限位、奇异性、
碰撞和轨迹连续性评估。DexCatch 不进入实时遥操闭环，本仓库也不修改它的项目叙事。
