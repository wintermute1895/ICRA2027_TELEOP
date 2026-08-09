# LBot Teleoperation (teleop_control_bridge)

## 简介
`teleop_control_bridge` 功能包实现了 Linker 机械臂的主从遥操作控制功能。它充当主臂 (LinkerTA 示教臂) 和 从臂 (LBot 真实机械臂) 之间的桥梁，将主臂的关节运动实时映射到从臂执行。

本系统包含以下特性：
- **主从同步**：支持左/右双臂独立或同时遥操作。
- **安全启动**：提供首次位置同步功能 (First Move)，启动时从臂会自动以安全速度平滑移动到主臂当前姿态，避免因为位置不一致导致的猛烈动作。
- **安全限位**：内置软限位检测，防止超出机械臂工作范围。
- **灵活配置**：支持关节映射重排序、比例缩放和自定义话题配置。

## 依赖项

在使用本功能包前，请确保工作空间包含以下包：
- `lbot_driver`: 真实机械臂驱动
- `linkerta`: 遥操臂驱动程序
- `lbot_arm_interfaces`: 自定义消息和服务接口

## 配置文件

主要配置文件位于 `config/hardware_teleop.yaml`，可根据实际需求调整：

### 从臂配置（一控一/一控多）

只需修改 `slave_arm_ips` 列表即可，系统会自动生成 `robot1`, `robot2`... 命名空间：

```yaml
# 一控一
slave_arm_ips:
  - "192.168.10.21"

# 一控二（添加第二个 IP）
slave_arm_ips:
  - "192.168.10.21"
  - "192.168.10.22"
```

### 核心参数
- `scale_factor` (默认: 1.0): 关节角度映射比例，1.0 代表 1:1 映射。
- `follow_mode` (默认: true): 是否开启实时跟随。
- `robot_type` (默认: "LS"): 机器人类型，LS是蓝思型号，RS是灵足V2
- `left_negation` / `right_negation`: 主臂 J1..J7 到从臂 J1..J7 的方向符号。`-1` 表示取反，`1` 表示保持；显式配置优先于 `robot_type` 默认值。

### 首次同步 (First Move)
- `first_move_speed` (默认: 0.2): 初始同步运动的关节速度 (rad/s)。
- `first_move_acce` (默认: 0.2): 初始同步运动的关节加速度 (rad/s^2)。

### 安全限位
- `enable_joint_limits`: 是否启用软件限位保护。


## 使用说明

### 1. 硬件连接
1. 确保 LBot 机械臂已连接电源。
2. 确保 LinkerTA 遥操臂通过 USB 连接至电脑（当前程序所在的电脑）。
3. 遥操臂和机械臂关节都在零位。

### 2. 启动CAN设备
```bash
sudo ip link set can0 up type can bitrate 1000000
```

### 3. 启动遥操作
使用提供的 launch 文件一键启动所有相关节点（驱动、遥操臂节点、桥接节点）：

```bash
ros2 launch teleop_control_bridge hardware_teleop.launch.py
```



### 4. 操作流程
1. **程序启动**：launch文件执行后，会依次启动 `lbot_driver` (从臂) 和 `linkerta` (主臂)。
2. **初始化**：`joint_mapping_bridge_node` 会订阅主臂数据并连接从臂服务。
3. **首次同步**：
   - 桥接节点检测主臂和从臂的当前的关节位置差异。
   - 驱动真实机械臂以较低的 `first_move_speed` 移动到与遥操臂一致的姿态。
   - **注意**：在此过程中请勿剧烈移动遥操臂。
4. **实时遥操**：
   - 同步完成后，进入跟随模式。
   - 操作人员移动 LinkerTA 遥操臂，LBot 机械臂将实时复现动作。

## 话题接口

- 订阅 (来自 linkerta)：
  - `/left_arm_joint_control` (`sensor_msgs/JointState`)
  - `/right_arm_joint_control` (`sensor_msgs/JointState`)

- 发布 (发送给 lbot_driver，每个从臂一套)：
  - `/robot1/left_arm/joint_follow` (`lbot_arm_interfaces/FollowJoint`)
  - `/robot1/right_arm/joint_follow` (`lbot_arm_interfaces/FollowJoint`)
  - `/robot2/left_arm/joint_follow` (如果有第二台从臂)
  - ...

## 常见问题

**Q: 机械臂启动后没有动作？**
A: 
1. 检查是否在 `hardware_teleop.yaml` 中启用了对应手臂 (`enable_left_arm` / `enable_right_arm`)。
2. 检查 CAN 总线通讯是否正常（lbot_driver 是否报错）。


**Q: 机械臂运动方向相反？**
A: 检查 `hardware_teleop.yaml` 中的关节映射或比例因子是否需要设置为负值，或者检查物理安装方向。
