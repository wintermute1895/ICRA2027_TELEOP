# ICRA2027_TELEOP 远程电脑交接文档

更新时间：2026-08-09

## 项目边界

这是 robot teleoperation/ICRA 2027 面向精密装配的 ROS2 主从遥操与多模态数采项目：LinkerTA
发布 ROS2 `JointState`，桥接节点完成关节顺序、方向、滤波和安全检查，再由 LK73
驱动调用官方 SDK 的 `joint_follow`。

DexCatch 是独立的离线质量评估项目。它可以读取本项目导出的 episode，计算 FK/IK、
关节限位、奇异性、轨迹连续性和数据质量，但不能接入本项目实时控制，也不应成为
真机遥操的运行时依赖。

仓库：`https://github.com/wintermute1895/ICRA2027_TELEOP.git`

## 仓库资产

- `ros2_ws/`：ROS2 Humble 驱动、接口、LinkerTA 节点和遥操桥接；
- `assets/robots/linker_platform/combined_robot/`：双臂和手部 URDF/mesh 资产；
- `tools/vendor_sdk/lbot_sdk_v103.py`：仅供方向检查工具使用的官方 SDK 1.0.3 handle ABI wrapper；
- `ros2_ws/src/lbot_driver/lib/`：ROS2 驱动使用的官方 SDK 动态库；
- `scripts/`：构建、启动、进程检查和 RunEvidence 采集入口；
- `tools/`：方向检查、时间同步诊断和 episode 导出工具。

历史 Python 手势遥操、旧版 1.0.1 Python SDK 直连和 AnyTeleop 原型已经移除，不能
再作为实验入口。

## 环境隔离与构建

ROS2 C++ 节点必须使用系统 ROS2 Humble，不要在 Conda 环境中构建：

```bash
git clone https://github.com/wintermute1895/ICRA2027_TELEOP.git
cd ICRA2027_TELEOP
./scripts/build_ros2_workspace.sh
source ros2_ws/install/setup.bash
```

执行环境预检：

```bash
python3 scripts/preflight.py --mode ros2
```

## 关节方向检查

先离线查看 URDF 和方向标记：

```bash
./scripts/run_joint_direction_check.sh --headless
```

真机测试必须有现场安全员保持物理急停可达：

```bash
./scripts/run_joint_direction_check.sh \
  --live --ip ROBOT_IP --arms both --enable-arms \
  --confirm=MOVE_2_DEG_WITH_ESTOP_READY
```

工具逐关节低速点动并回读 SDK 状态。官方 SDK 1.0.3 没有读取当前使能状态的接口，
工具只能显式调用 enable 并检查返回值，不能把软件结果当成物理安全证明。

## ROS2 遥操启动

只做预检：

```bash
./scripts/start_hardware_teleop.sh
```

桥接节点默认 `armed=false`。现场确认急停、设备周围无人、关节方向和限位后，才可：

```bash
./scripts/start_hardware_teleop.sh \
  --real --confirm=I_UNDERSTAND_REAL_ROBOT
```

## 精密装配数采

默认 observation 模式不向机械臂发送遥操命令：

```bash
bash scripts/start_capture_session.sh \
  --episodes=1 --duration-s=30
```

真机遥操采集必须额外确认物理急停：

```bash
bash scripts/start_capture_session.sh \
  --real \
  --physical-estop-ready \
  --confirm=I_UNDERSTAND_REAL_ROBOT \
  --episodes=1 --duration-s=30
```

脚本会检查重复进程、ROS2 节点、相机序列号、CAN、机器人地址、磁盘空间、关节限位
和 One-Euro 滤波配置，并在 tmux 中分别启动驱动、RealSense、桥接、预览、监控、同步
诊断和 RunEvidence recorder。

默认相机配置为 `640x480@15`，RGB/深度启用同步和深度对齐。episode 至少包含：

- 主端原始/滤波/映射后关节数据；
- 从臂关节状态；
- RGB、对齐深度和相机内参；
- `/tf`、`/tf_static`；
- URDF、映射配置和时间同步报告。

## DexCatch 离线评估

采集结束后，单独在 DexCatch 环境中评估数据质量：

```bash
python /path/to/DexCatch/tools/evaluate_episode_quality.py \
  --episode evidence/teleop/<episode> \
  --output quality_report.json
```

评估报告作为 RunEvidence 的派生 artifact 保存，不得发布到实时遥操 topic，也不得
调用 `joint_follow` 或使能真机。

## 交接完成标准

- ROS2 工作区构建成功；
- 默认启动保持 disarmed；
- 相机与关节话题能被 recorder 发现；
- 时间戳诊断报告生成；
- 方向检查工具可运行；
- 精密装配 episode 能保存；
- DexCatch 能离线读取 episode 并输出质量报告。

在这些条件完成前，禁止把离线评估结果描述为真机装配成功，也禁止跳过物理急停和
低速方向确认直接进入长时间真机采集。
