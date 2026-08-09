# VIST 遥操系统快速开始

仓库中有两条明确分开的链路：

- `arm_teleop`：ROS 2 C++ 真机主从遥操，LinkerTA 主臂通过 ROS 2 话题驱动 LK73 从臂。
- `IROS_teleop`：Python 视觉、手部重定向、Pinocchio/Pink 和 MeshCat 原型。

不要在同一个 Python 进程里混用 ROS 2 系统 Python 和 Conda。ROS 2 C++ 节点使用系统环境；Python 视觉/IK 使用 `mpc_env`。如果 Python 节点确实需要 `rclpy`，也必须用 `source /opt/ros/humble/setup.bash` 后在 `mpc_env` 中单独启动，并且不能让 Conda 的库路径进入 C++ 节点。

## 1. 环境检查

```bash
cd ~/ICRA2027_TELEOP
python3 scripts/check_teleop_environment.py --mode ros2
conda run -n mpc_env python scripts/check_teleop_environment.py --mode python
```

`can0` 缺失只会给出警告，因为 mock 和纯仿真不需要 CAN。SDK 动态库和 URDF 属于代码仓库内的静态检查项。

## 2. Python mock 闭环

```bash
./scripts/run_mock_teleop.sh --headless
```

默认启动 `mpc_env`，发送 21 点手部关键点到 `127.0.0.1:5005`，接收端使用仓库内的 URDF 做重定向。需要 MeshCat 时去掉 `--headless`，控制器会打开 MeshCat viewer。也可以单独调试：

```bash
conda run -n mpc_env python IROS_teleop/control_anyteleop.py --no-viewer
conda run -n mpc_env python IROS_teleop/mock_vision.py --fps 30
```

收到坏包时会显示明确的 JSON、字段或形状错误，不再静默吞掉异常。

## 3. 构建 ROS 2

构建脚本会清除 Conda 变量和库路径后再 source ROS 2，避免 ABI 污染：

```bash
./scripts/build_ros2.sh
source arm_teleop/install/setup.bash
```

修改 ROS 2 C++ 代码后重复运行构建脚本即可。不要先 `conda activate` 再直接运行 `colcon build`。

## 4. 真机启动安全闸门

普通运行只做检查，不启动真机：

```bash
./scripts/run_ros2_teleop.sh
```

直接 `ros2 launch lbot_teleop teleop.launch.py` 时，桥接节点的 `armed` 默认是 `false`，不会把主臂数据转发给从臂。真机运行需要操作员明确确认：

```bash
./scripts/run_ros2_teleop.sh --real --confirm=I_UNDERSTAND_REAL_ROBOT
```

这不是替代物理安全措施。测试前必须确认机械臂周围无人、急停可触达、控制器和主臂均处于预期状态，并先用低速小范围动作验证关节方向。脚本不会自动关闭急停，也不会提供免密码 sudo。

`IROS_teleop/Remote Robot/02_teleop_run.py` 是旧的直连 SDK 入口，缺少主链路的完整限位和 ROS2 桥接保护，默认已拒绝运行。实验室测试应使用上面的 `scripts/run_ros2_teleop.sh`。

桥接节点还会拒绝：

- 非 7 关节或映射索引无效的消息；
- NaN/Inf 关节值；
- 超出配置安全限位的整帧命令。

当前限位是配置层保护，不等同于经过真机标定的厂商限位；必须用目标机械臂型号、左右臂方向和实际 TCP 标定值复核 `arm_teleop/src/lbot_teleop/config/teleop_config.yaml` 后再上电。

## 4.1 RunEvidence 遥操与相机数采

首次配置还需要安装 ROS2 的图像传输插件。它不是 Python/Conda 依赖，必须在
Ubuntu 系统环境中安装：

```bash
sudo apt update
sudo apt install -y ros-humble-image-transport-plugins
```

如果当前终端不能交互输入 sudo 密码，这一步需要在本机真实终端手动执行；不能用
`sudo -n` 绕过密码。安装后确认：

```bash
source /opt/ros/humble/setup.bash
ros2 pkg prefix image_transport_plugins
```

遥操数采不需要启动 `armed` 桥接。建议先启动 LinkerTA、RealSense ROS2 驱动和（如需记录真机反馈）lbot_driver，再用 RunEvidence 包装只读 recorder：

```bash
conda activate mpc_env
source /opt/ros/humble/setup.bash
source arm_teleop/install/setup.bash

runevidence run --domain robotics \
  --runs-root evidence/teleop \
  --label teleop-capture \
  --input urdf=IROS_teleop/config/combined_robot/robot.urdf \
  --input teleop_config=arm_teleop/src/lbot_teleop/config/teleop_config.yaml \
  -- bash scripts/run_teleop_evidence_capture.sh
```

默认记录 60 秒；可用 `TELEOP_CAPTURE_DURATION_S=300` 修改。脚本只调用
`ros2 bag record`，不启动驱动、不发布 `joint_follow`，并把 bag 和
`teleop_capture_manifest.json` 放入 RunEvidence 的 `artifacts/`。rosbag 的索引使用
录制端接收时间，而每条 `Image`、`CameraInfo`、`JointState` 消息内部的
`header.stamp` 会原样保留；跨设备对齐时应优先使用消息头时间戳，并在实验开始前
确认相机、ROS2 驱动和机器人节点使用同一个 ROS clock。不要用文件修改时间代替
传感器时间。

官方 `realsense2_camera/rs_launch.py` 默认同时使用 `camera_namespace=camera` 和
`camera_name=camera`，因此原始话题为 `/camera/camera/...`，recorder 已将它作为
默认值。如果使用自定义 launch 产生 `/camera/...`，启动 recorder 时显式设置：

```bash
REALSENSE_NAMESPACE=/camera runevidence run ... -- \
  bash scripts/run_teleop_evidence_capture.sh
```

当前 recorder 已验证以下安全性质：它不启动驱动、不发布 `joint_follow`、不改变
机械臂使能状态；即使 `~/.ros/log` 不可写，ROS2 日志也会落到 RunEvidence 的
`system/ros_logs/`，不会因此导致录制进程异常退出。没有实际 ROS 话题时，离线
smoke test 会产生合法的空 bag；真实采集时必须检查 bag metadata 中的
`message_count` 和 topic 计数，避免把空录制当成有效数据。

## 4.2 时间同步诊断

在已经启动 RealSense ROS2 驱动、LinkerTA 和（可选的）lbot_driver 后，使用系统
ROS2 Python 运行：

```bash
unset CONDA_PREFIX CONDA_DEFAULT_ENV PYTHONHOME PYTHONPATH
export PATH=/opt/ros/humble/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
source /opt/ros/humble/setup.bash
python3 tools/diagnose_ros_time_sync.py \
  --duration-s 20 \
  --camera-namespace /camera/camera \
  --output evidence/teleop/time_sync_report.json
```

报告会给出每个 topic 的消息数量、header 时间间隔、时间戳年龄、周期 MAD 抖动，
以及 RGB/深度、主端控制/机器人状态之间的最近时间差。没有启动 lbot_driver 时，
机器人状态对应项会明确标记为 `missing`，不能把这种报告当成完整硬件同步通过。

RealSense 的 RGB/深度帧内同步使用驱动的 `enable_sync:=true`；机器人状态优先使用
官方 SDK 返回的 `sec/nanosec`，驱动无法获得有效控制器时间戳时才回退到 ROS 接收时刻。
跨电脑实验还需要 Chrony/PTP 或硬件触发，并在报告中声明，不能仅凭 rosbag 文件时间
宣称完成硬件同步。

## 5. 环境维护

Python 环境可以依据 `IROS_teleop/environment.yml` 重建：

```bash
conda env create -f IROS_teleop/environment.yml
```

`requirements.txt` 也已移除开发机本地构建路径，可用于已有 Python 3.10 环境；新机器仍优先使用 `environment.yml`，因为它同时固定了 Python 版本。

## 6. 关节方向检查

该工具直接调用仓库内官方 SDK 1.0.3 的 handle ABI，不经过旧版 1.0.1 Python wrapper。它验证的是“SDK 正关节角与 URDF 正方向是否一致”，不是 LinkerTA 主臂到从臂的最终 `negation`。

先离线检查完整 URDF 和 14 个关节的 MeshCat 预演：

```bash
./scripts/run_joint_direction_check.sh
```

无浏览器环境使用：

```bash
./scripts/run_joint_direction_check.sh --headless
```

真机测试前必须满足：机械臂周围无人；物理急停由另一人保持可触达；左右臂当前姿态距离 URDF 限位至少 5 度；实验员理解工具会显式使能所选机械臂。官方 SDK 1.0.3 没有“读取当前使能状态”的接口，因此工具只能显式调用 `lbot_enable_arm(..., true)` 并检查返回值，不能声称读取到了使能状态。

```bash
./scripts/run_joint_direction_check.sh \
  --live \
  --ip 192.168.10.21 \
  --arms both \
  --enable-arms \
  --confirm=MOVE_2_DEG_WITH_ESTOP_READY
```

默认参数是 2 度、`0.05 rad/s`、`0.05 rad/s²`。工具拒绝超过 3 度或 `0.10 rad/s` 的测试。

每个关节的操作顺序：

1. MeshCat 先显示正方向目标，红球标出当前关节。
2. 按空格后，工具通过官方 `lbot_move_joint` 做正向点动。
3. SDK 回读角度必须至少达到命令增量的 25%，否则中止。
4. 观察真机与 MeshCat，按 `y` 表示同向、`n` 表示反向、`u` 表示无法判断。
5. 按空格后返回该关节的测试前角度，再测试下一个关节。

顺序为 `L1, R1, L2, R2, ... L7, R7`。按 `s` 跳过，按 `q` 返回当前测试关节后退出。发生异常时工具会尽力返回该关节的起始角，但不会自动掉使能，因为机械臂突然失力可能更危险；退出后必须通过示教器或实验室批准流程处理使能状态。

默认报告位置：

```text
reports/joint_direction_report.json
```

其中 `sdk_to_urdf_sign=1` 表示同向，`-1` 表示反向。报告记录 SDK/URDF SHA256、控制器型号、每次运动前后角度、回零误差和实验员判断。

## 当前边界

驱动现在按官方 SDK 约定把 `handle.id > 0` 判为连接成功。SDK 的 FK/IK、关节限位接口是否在具体控制器固件上实现，仍需通过官方返回值和错误日志在真机上确认；本仓库不会把 URDF 限位冒充 SDK 限位，也不会因为 URDF 仿真通过就宣称真机安全。
