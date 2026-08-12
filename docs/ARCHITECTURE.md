# Robot teleoperation platform architecture

本仓库是通用的机器人遥操与多模态数据平台，不绑定论文标题。论文问题、A/B 条件和
任务定义属于 experiment profile；设备、控制和数据契约保持稳定。

```text
experiment/   任务、条件、随机化、指标和数据质量门
capture/      episode 生命周期、rosbag2、RunEvidence、时间同步
control/      单位适配、关节映射、滤波、安全门和硬件命令
devices/      LinkerTA、LK73、RealSense 等 ROS2 adapter
interfaces/   ROS2 messages/services、episode schema 和单位约定
evaluation/   只读离线评估；可调用 DexCatch 的运动学与规划能力
```

## 当前代码映射

| 层 | 位置 |
|---|---|
| devices | `ros2_ws/src/linkerta`、`ros2_ws/src/lbot_driver` |
| interfaces | `ros2_ws/src/lbot_arm_interfaces`、`docs/EPISODE_SCHEMA_V1.md` |
| control | `ros2_ws/src/teleop_control_bridge` |
| capture | `scripts/start_capture_session.sh`、`scripts/record_episode.sh` |
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

任务、reference、policy、安全和 evaluation profile 由
`tools/resolve_experiment_manifest.py` 解析为不可变 manifest。条件采用
`nominal_reference_v1` 等版本化 ID，论文中的 A/B/B0/B1/B2 只是 profile 的角色
映射。任务以 `ContactRichPrecisionAssemblyTask` 作为有边界的基类，而 USB-C 是
连接器插接子类的具体场景；详见 `docs/EXPERIMENT_MANIFESTS.md`。

## DexCatch 边界

DexCatch 是独立抓取项目。本仓库只把已录制 episode 交给它做 FK/IK、限位、奇异性、
碰撞和轨迹连续性评估。DexCatch 不进入实时遥操闭环，本仓库也不修改它的项目叙事。
