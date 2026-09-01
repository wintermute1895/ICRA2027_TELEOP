# Robot teleoperation platform quick start

本仓库提供通用的双臂遥操和多模态数采链路：LinkerTA 主臂通过 ROS2 桥接驱动 LK73
从臂，同时记录关节、相机、时间戳和操作者指令。具体任务由 experiment profile 定义。

DexCatch 不属于本仓库的运行时控制链路。它只对本仓库产生的 episode 做离线
FK/IK、限位、奇异性、轨迹连续性和数据质量评估。

## 项目结构

```text
ros2_ws/                      ROS2 workspace、设备 adapter 和控制包
assets/robots/linker_platform/ URDF、mesh 和关节命名资产
config/experiments/           A/B 条件和控制 profile
scripts/                      构建、启动、数采和预检入口
third_party/linkerbot_sdk/    官方 SDK 动态库和 Python ABI wrapper
docs/                         架构、数据契约、实验和安全说明
```

旧的 Python 手势遥操、旧版 Python SDK 直连和 AnyTeleop 原型已经从正式仓库移除，
避免把它们误认为精密装配主链路。

## 环境与构建

ROS2 C++ 工作区不要在 Conda 环境中构建：

```bash
./scripts/build_ros2_workspace.sh
source ros2_ws/install/setup.bash
```

ROS2 主链路使用系统 Python；RunEvidence 和离线分析可使用项目指定的 Python 环境。

## 只读预检

```bash
python3 scripts/preflight.py --mode ros2
```

预检不会连接或使能机械臂。

## 真机遥操

先运行预检：

```bash
./scripts/start_hardware_teleop.sh
```

确认机械臂周围无人、急停可触达、LinkerTA 与从臂状态正确后，才允许真机：

```bash
./scripts/start_hardware_teleop.sh \
  --real \
  --confirm=I_UNDERSTAND_REAL_ROBOT
```

桥接节点默认不 armed；真机运行必须显式确认。控制器单位为弧度，关节限位、左右
方向映射和 One-Euro 滤波均在 ROS2 桥接中执行。

## 精密装配数采

完整采集入口会检查 ROS2 工作区、CAN、相机、机器人地址、进程冲突、磁盘空间、
关节限位和滤波配置。默认是安全 observation 模式，不向机械臂发送遥操命令：

```bash
bash scripts/start_capture_session.sh \
  --episodes=1 \
  --duration-s=30
```

连接 tmux：

```bash
tmux attach -t teleop_capture
```

只有经过现场安全确认，才允许发送真机遥操：

```bash
bash scripts/start_capture_session.sh \
  --real \
  --physical-estop-ready \
  --confirm=I_UNDERSTAND_REAL_ROBOT
```

相机、episode 循环、采集模式、任务与人员 ID 都从默认的
`config/capture_session.env` 读取；临时实验可用 `--config=PATH` 切换配置。
真机急停与授权参数不能写入配置文件。

相机默认使用 `640x480@15`，RGB 和深度启用同步与深度对齐。每个 episode 由
RunEvidence 管理，至少记录：

- 主端原始、滤波后和映射后关节状态；
- 从臂左右关节状态；
- RGB、对齐深度和相机内参；
- `/tf`、`/tf_static`；
- 配置、URDF、时间同步报告和运行元数据。

## 时间同步诊断

在相机、LinkerTA 和可选的机器人驱动都启动后运行：

```bash
unset CONDA_PREFIX CONDA_DEFAULT_ENV PYTHONHOME PYTHONPATH
source /opt/ros/humble/setup.bash
python3 tools/diagnose_time_sync.py \
  --duration-s 20 \
  --camera-namespace /camera/camera \
  --output evidence/teleop/time_sync_report.json
```

报告测量 ROS2 `header.stamp` 一致性，不能单独宣称完成硬件触发、PTP 或跨电脑硬件
同步。

## 关节方向检查

离线查看 URDF：

```bash
./scripts/run_joint_direction_check.sh --headless
```

真机测试必须另有实验员保持物理急停可达，并使用低速、小角度和显式确认参数。该
工具调用官方 SDK 1.0.3，只验证方向和回读，不替代厂商限位或物理安全措施。

## 与 DexCatch 的离线联动

采集完成后，将 episode 交给 DexCatch 的评估工具：

```bash
python /path/to/DexCatch/tools/evaluate_episode_quality.py \
  --episode evidence/teleop/<episode> \
  --output quality_report.json
```

评估结果应作为同一 RunEvidence 实验的派生 artifact 保存，不得反向接入实时遥操
控制节点。

A/B 条件、质量门和统计建议见
[docs/EXPERIMENT_AND_SCORING.md](docs/EXPERIMENT_AND_SCORING.md)。
