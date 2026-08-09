# 机器人模型与检查资产

这个目录不是第二套遥操系统，也不包含实时控制入口。

当前用途只有两类：

1. `config/combined_robot/` 提供精密装配实验使用的双臂/手部 URDF 和 mesh；
2. `tools/vendor_sdk/lbot_sdk_v103.py` 为 `tools/check_joint_directions.py` 提供官方 SDK 1.0.3 的
   最小 handle ABI 封装。

实时遥操必须从仓库根目录的 ROS2 入口启动：

```bash
./scripts/start_hardware_teleop.sh
```

不要从本目录直接启动控制节点，也不要把 DexCatch 的规划器接到这里。DexCatch 对
采集后的 episode 做离线运动学和数据质量评估。
