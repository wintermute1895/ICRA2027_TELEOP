# ICRA2027_TELEOP

面向精密装配研究的 ROS2 双臂遥操与多模态数采系统。

主链路为：

```text
LinkerTA → ROS2 关节状态 → 滤波/方向映射 → 安全桥接 → LK73
                         ↓
              RGB-D、关节、TF、时间戳
                         ↓
                    RunEvidence
```

本项目负责实时实验平台：真机驱动、仿真接口、遥操映射、安全机制、相机采集、时间
同步和 episode 记录。DexCatch 是独立的离线工具，只用于对 episode 做运动学和数据
质量评估，不是本项目的运行时规划器，也不参与真机遥操。

详细入口见 [TELEOP_QUICKSTART.md](TELEOP_QUICKSTART.md)。
