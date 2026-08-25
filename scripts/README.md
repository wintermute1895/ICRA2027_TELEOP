# D0 遥操录包（相机 + 机械臂 + 手）

这套脚本把三类数据录进同一个 ROS2 bag：

- 相机：`--camera-topics` 直接录压缩话题，或 `--camera-republish` 把 raw 图实时转成压缩图再录；
- 机械臂：遥操主端 `/joint_error_code`、`/{left,right}_arm_joint_control`、`/vist/{side}/*`，以及 `--require-robot-state` 启用的真实关节/位姿状态；
- 手：默认录 O6 的 `/robot1/right_hand/set_l6_joint`（六关节 `UInt8MultiArray` 指令流）；L10 使用 `/robot1/right_hand/set_l10_joint`，可用 `--hand-side`、`--hand-model l10`、`--hand-topic` 调整。

## 环境

先构建一次 `arm_teleop`（把 5 个包装进 ASCII 工作空间 `/home/pao/icra2027_teleop_ws`）：

```bash
cd /home/pao/桌面/ICRA2027_TELEOP
./scripts/build_arm_teleop.sh
```

脚本强制使用系统 Python 3.10（conda 的 Python 会缺少 empy 导致 ROS2 接口生成失败），并把构建/安装目录放在纯 ASCII 路径下（仓库路径含中文“桌面”，ROS2 接口生成会丢掉中文段）。之后 `scripts/d0_env.sh` 默认 `source` 的就是这个工作空间；如需指向其它位置：

```bash
export ARM_TELEOP_WORKSPACE=/path/to/arm_teleop
```

## 一键起四个窗口

```bash
cd /home/pao/桌面/ICRA2027_TELEOP
./scripts/tmux_d0.sh
```

它会依次打开：

- `camera`：RealSense（640x480@15；本机 realsense2_camera 为 2023 版，
  分辨率用 `rgb_camera.color_profile` / `depth_module.depth_profile` 设置，
  旧式 `color_width:=...` 参数会被忽略并跑在默认 30fps）
- `teleop`：`ros2 launch lbot_teleop teleop.launch.py armed:=true`
- `hand`：O6 GUI 手部控制器（`can0` 直接控制实物手，并持续镜像到
  `/robot1/right_hand/set_l6_joint`，因此会被录入 rosbag）
- `record`：进入项目根目录，准备执行记录命令

## 录制一条 episode

录包时如需弹窗查看 RealSense 视角，在命令中加入 `--camera-preview`。窗口显示彩色图和深度图，按 `q` 或 Esc 可关闭预览；关闭预览不会停止录包。

先确保没有旧节点残留（`tmux_d0.sh` 会自动清理；手动场景执行
`./scripts/stop_teleop.sh`），然后在 `record` 窗口（或任何已
`source scripts/d0_env.sh` 的终端）执行：

```bash
cd /home/pao/桌面/ICRA2027_TELEOP
python3 scripts/d0_record.py \
  --episode-id d0_right_hand_001 \
  --arm right --require-robot-state \
  --camera-topics /camera/camera/color/image_raw \
  --camera-topics /camera/camera/depth/image_rect_raw \
  --camera-topics /camera/camera/color/camera_info \
  --camera-preview \
  --task-id D0-RIGHT-HAND-001 \
  --task-description "右臂遥操+相机+O6手" \
  --hardware-commands-enabled
```

推荐直接录 raw 相机话题（约 1.4GB/min，控制单条时长即可），这是真机验证过的
路径；`--camera-republish` 压缩转发方式可选但稳定性较差，遇到 republish 输出
话题没有发布者时请改用上面的 raw 直录。

动作完成后在 record 窗口按 `Ctrl-C` 停止。

## 分流审计

```bash
python3 scripts/d0_split.py \
  --episode-id d0_right_hand_001 \
  --success true
```

手部话题缺失、为空、或 O6 关节数不是 6 都会自动判进 `A_audit`，不会被误收为完整样本。
