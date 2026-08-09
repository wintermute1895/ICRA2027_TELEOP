# ICRA2027_TELEOP 远程电脑交接文档

更新时间：2026-08-07

## 项目边界

这是 VIST/ICRA 2027 的 ROS2 主从遥操项目：LinkerTA 主臂发布 ROS2 `JointState`，桥接节点转换关节顺序/方向后，由 LK73 驱动调用官方 SDK 的 `joint_follow`。它不是 DexCatch 抓取项目，不负责抓取目标检测、Pink 抓取规划或 `move_joint` 计划。

```text
仓库：https://github.com/wintermute1895/ICRA2027_TELEOP.git
分支：ldk
```

## 仓库内资产

- `arm_teleop/`：ROS2 Humble C++ 驱动、接口、LinkerTA 和遥操桥接；
- `IROS_teleop/`：Python 视觉/手部重定向/Pinocchio/Pink/MeshCat 原型；
- `arm_teleop/src/lbot_driver/lib/`：官方 SDK 1.0.3 C/C++ 动态库；
- `IROS_teleop/lbot/libs/`：历史 1.0.1 Python ABI，仅用于旧代码，不能和 1.0.3 wrapper 混用；
- `IROS_teleop/config/combined_robot/`：完整双臂 + 手 URDF 和 meshes；
- `tools/check_joint_directions.py`：直接按官方 1.0.3 handle ABI 做关节方向检查。

不要从另一台机器拷贝软件、SDK、URDF 或 STL。它们已经跟踪在 Git 中。远程 AI 必须记录 `git rev-parse HEAD`、SDK 动态库路径和 URDF SHA256。

## ROS2/Conda 隔离

ROS2 C++ 节点使用系统 ROS2 Humble；Python 视觉和 MeshCat 使用 Conda `mpc_env`。不要把 Conda 环境写入 ROS2 C++ 构建过程，也不要依赖 `.bashrc` 自动 source 顺序。

```bash
git clone --branch ldk https://github.com/wintermute1895/ICRA2027_TELEOP.git
cd ICRA2027_TELEOP

# 系统 ROS2 构建
./scripts/build_ros2.sh

# Python 环境
conda env create -f IROS_teleop/environment.yml
```

如果已有 `mpc_env`，不要覆盖它，先执行环境检查：

```bash
python3 scripts/check_teleop_environment.py --mode ros2
conda run -n mpc_env python scripts/check_teleop_environment.py --mode python
```

## 本地 mock 验证

```bash
./scripts/run_mock_teleop.sh --headless
```

这个闭环只使用 21 点 mock hand 数据、手部 URDF 和重定向器，不连接机器人、不启用机械臂。需要 MeshCat 时去掉 `--headless`。

## 关节方向验证

先离线预演 14 个关节：

```bash
./scripts/run_joint_direction_check.sh
```

真机方向测试必须在现场有物理急停安全员后执行：

```bash
./scripts/run_joint_direction_check.sh \
  --live --ip ROBOT_IP --arms both --enable-arms \
  --confirm=MOVE_2_DEG_WITH_ESTOP_READY
```

工具按 `L1,R1,L2,R2,...` 交替测试，默认每次正向点动 2°，速度和加速度均为 `0.05`。每次点动后回读 SDK 状态，并由现场人员判断真机和 MeshCat 是否同向。报告写入 `reports/joint_direction_report.json`，其中 `sdk_to_urdf_sign` 只表示 SDK 与 URDF 的关系，不能直接当作主从 `negation` 配置。

官方 SDK 1.0.3 没有读取当前使能状态的接口，因此工具会显式发送 enable=true 并检查返回值；它不会自动解除急停，也不会在退出时自动掉使能。

## ROS2 遥操启动

普通命令只做预检：

```bash
./scripts/run_ros2_teleop.sh
```

桥接节点 `armed` 默认是 `false`，直接 launch 不会转发运动命令。只有现场确认后才能：

```bash
./scripts/run_ros2_teleop.sh \
  --real --confirm=I_UNDERSTAND_REAL_ROBOT
```

首次真机联调必须先关闭不需要的手臂，在低速、小范围、空载状态下逐关节确认方向，再开始连续遥操。当前 ROS2 桥接还会拒绝非 7 关节、NaN/Inf 和超出配置限位的整帧命令。

## 当前未完成项

- 主臂 LinkerTA 与 LK73 从臂的最终方向/偏置仍需现场逐关节确认；
- `teleop_config.yaml` 的 `negation`、mapping、机型和限位必须和现场设备复核；
- CAN 设备、LinkerTA 权限、机器人 IP 和控制器状态只能在现场确认；
- 官方 SDK 没有 enable-state getter，不能从软件证明当前物理使能状态；
- 网络中断、急停和控制器停止距离需要现场测试；
- 不能把 DexCatch 的抓取规划、视觉目标和 `move_joint` 代码接入本项目。

## 远程 AI 完成标准

在远程电脑报告“环境完成”前，必须完成：仓库分支正确、SDK/URDF 可读、ROS2 构建成功、Conda 依赖可导入、mock 闭环通过、方向工具离线 14 关节通过、默认 ROS2 启动保持 disarmed。以上阶段禁止连接或运动真机。
