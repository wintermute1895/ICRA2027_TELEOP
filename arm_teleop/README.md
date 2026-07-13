# LBot ROS2 机械臂控制系统

> **版本: v1.0.0**

本仓库包含 Linker 机械臂的 ROS2 控制系统，支持双臂驱动、遥操作控制和示教功能。

## 功能包概述

| 功能包 | 说明 |
|--------|------|
| `lbot_arm_interfaces` | 自定义消息和服务接口定义 |
| `lbot_driver` | 真实机械臂驱动程序 |
| `lbot_teleop` | 遥操作桥接（主从臂控制） |
| `linkerta` | LinkerTA 遥操臂驱动 |
| `lbot_demo` | 示例程序和演示 |

## 系统要求

- Ubuntu 22.04 / 24.04
- ROS2 Humble / Jazzy
- C++17 编译器

## 编译

### 1. 安装依赖

```bash
rosdep install --from-paths src --ignore-src -r -y
```

### 2. 编译所有功能包

```bash
colcon build --symlink-install
```


### 3. 设置环境

```bash
source install/setup.bash
```

建议将此命令添加到 `~/.bashrc`：

```bash
echo "source ~/ros2/install/setup.bash" >> ~/.bashrc
```

## 快速开始

### 遥操作模式

详细说明请参考 [lbot_teleop/README.md](src/lbot_teleop/README.md)

```bash
# 一键启动遥操作（驱动 + 遥操臂 + 桥接）
ros2 launch lbot_teleop teleop.launch.py
```

### 仅启动机械臂驱动

```bash
ros2 launch lbot_driver lbot_start_driver.launch.py
```



## 配置文件

| 文件路径 | 说明 |
|----------|------|
| `src/lbot_teleop/config/teleop_config.yaml` | **主配置文件**：从臂IP列表、机型、限位、话题等 |
| `src/lbot_driver/config/lbot_config.yaml` | 机械臂驱动默认参数 |
| `src/linkerta/config/lta.yaml` | 遥操臂配置 |

### 从臂配置示例

只需在 `teleop_config.yaml` 中修改 IP 列表即可实现一控一或一控多：

```yaml
# 一控一
slave_arm_ips:
  - "192.168.10.21"

# 一控二（取消注释第二个 IP）
slave_arm_ips:
  - "192.168.10.21"
  - "192.168.10.22"
```

系统会自动生成 `robot1`, `robot2`... 命名空间。

## 机型支持

通过 `teleop_config.yaml` 中的 `robot_type` 参数选择机型：

- `"LS"`: LS 系列机械臂 蓝思机械臂
- `"RS"`: RS 系列机械臂 灵足V2

不同机型会自动应用对应的关节限位和方向修正。

## 常见问题

**Q: 编译报错找不到 lbot_arm_interfaces？**

A: 确保先编译接口包：
```bash
colcon build --packages-select lbot_arm_interfaces
source install/setup.bash
colcon build
```

**Q: CAN 通讯失败？**

A: 检查：
1. CAN 设备是否正确连接
2. 运行 `ip link show` 确认 CAN 接口存在
3. 确保有足够权限访问 CAN 设备


