# robot teleoperation episode schema v1

仿真和真机都必须把一次实验表达为同一组语义字段。传输方式可以不同：真机使用
ROS2 bag，仿真可以使用 ROS2 bag 或 JSONL；字段含义不能改变。

| 字段 | 单位 | 仿真来源 | 真机来源 |
|---|---|---|---|
| `master_joint_raw` | source-defined, 必须声明 | mock/LinkerTA 输入 | LinkerTA ROS2 `JointState` |
| `master_joint_filtered` | rad | One Euro 中间层 | One Euro 中间层输出 |
| `mapped_joint_command` | rad | 仿真控制输入 | teleop_control_bridge 映射后的命令 |
| `robot_joint_state` | rad | MuJoCo qpos/qvel | lbot_driver `JointState` |
| `tcp_pose` | m/rad | MuJoCo 或 Pinocchio FK | driver pose 或同一 URDF FK |
| `rgb` | image | MuJoCo renderer（可选） | RealSense `Image` |
| `depth` | uint16/depth unit | MuJoCo renderer（可选） | RealSense aligned depth |
| `camera_info` | calibration | 仿真相机模型 | RealSense `CameraInfo` |
| `tf` | transform | 仿真 TF | ROS2 `/tf` 和 `/tf_static` |
| `quality_score_A` | [0,1] | 离线/在线 scorer | 离线/在线 scorer |
| `success` | boolean/unknown | 仿真任务判定 | 人工或任务检测器标签 |

每条记录至少包含：

```json
{
  "episode_id": "...",
  "source_domain": "sim|real",
  "sample_index": 0,
  "header_stamp_ns": 0,
  "receipt_stamp_ns": 0,
  "clock_source": "ros|mujoco|controller",
  "arm": "left|right|both",
  "joint_names": [],
  "robot_joint_state_rad": [],
  "mapped_joint_command_rad": [],
  "tcp_pose_base": {},
  "quality_score_A": null,
  "success": null
}
```

仿真必须使用 MuJoCo simulation clock；真机机器人状态优先使用 SDK 返回的
`sec/nanosec`，相机和控制消息使用 ROS2 `header.stamp`。`receipt_stamp_ns` 只用于
估计传输延迟，不能替代传感器时间。
