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
./scripts/start_hardware_teleop.sh
./scripts/start_capture_session.sh --episodes=1 --duration-s=30
```
