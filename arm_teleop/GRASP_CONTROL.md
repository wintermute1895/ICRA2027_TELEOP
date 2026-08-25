# 灵巧手三段式抓取

`demo_hand_grasp_control` 通过仓库已有的 L6/L10 SDK 话题控制灵巧手：

| 状态 | 含义 |
| --- | --- |
| `0` | 完全张开 |
| `1` | 预抓取（手指半闭合，保留物体进入空间） |
| `2` | 抓取 |

先启动 `lbot_driver`，再启动控制节点。默认控制 `robot1` 的双只 L10 手：

当前仓库路径包含中文，ROS2 Humble 的接口生成器会因此生成错误的包索引。请使用已修复的 overlay：

```bash
source /opt/ros/humble/setup.bash
source /home/pao/桌面/ICRA2027_TELEOP/arm_teleop/install.grasp/setup.bash
```

```bash
ros2 run lbot_demo demo_hand_grasp_control
```

启动时也可以指定型号、手侧和初始状态：

```bash
ros2 run lbot_demo demo_hand_grasp_control --ros-args \
  -p robot_namespace:=robot1 -p hand_type:=l10 -p side:=right -p state:=0
```

运行中切换状态：

```bash
ros2 topic pub --once /hand/grasp_state std_msgs/msg/UInt8 "{data: 1}"
ros2 topic pub --once /hand/grasp_state std_msgs/msg/UInt8 "{data: 2}"
ros2 topic pub --once /hand/grasp_state std_msgs/msg/UInt8 "{data: 0}"
```

也可以用名字调用手势。内置名称是 `open`、`pregrasp`、`grasp`：

```bash
ros2 topic pub --once /hand/gesture std_msgs/msg/String "{data: pregrasp}"
ros2 topic pub --once /hand/gesture std_msgs/msg/String "{data: grasp}"
```

自定义手势通过参数传入。下面例子新增一个 `pinch`，L10 每个手势需要 10 个关节值：

```bash
ros2 run lbot_demo demo_hand_grasp_control --ros-args \
  -p gesture_names:="['pinch']" \
  -p gesture_positions:="[120, 128, 30, 180, 180, 180, 128, 128, 128, 220]"
```

自定义多个手势时，`gesture_positions` 按手势顺序连续排列；也可以加 `-p gesture:=pinch`，让节点启动后直接进入该手势。

L6 手使用 `-p hand_type:=l6`。默认位置值来自 SDK 示例；不同手或物体尺寸可通过 `l6_*`/`l10_*` 参数覆盖，每组必须分别提供 6 或 10 个 `0..255` 数值。

## 实时示教

启动驱动后，在另一个终端运行：

```bash
cd /home/pao/桌面/ICRA2027_TELEOP/arm_teleop
source /opt/ros/humble/setup.bash
source install.grasp/setup.bash
python3 teach_hand_gestures.py
```

示教器默认控制 `robot1` 右手 L10。按 `r` 开始调节；按 `1-9` 或 `0` 选择 10 个自由度；方向键实时调节当前值；`[`/`]` 调整步长；按 Enter 输入标签并保存；按 Esc 保存全部手势并退出。

手势保存在 `hand_gestures.json`。其他 Python 脚本可以直接调用：

```python
from hand_gestures import execute_gesture

execute_gesture("pinch")
```

也可以复用一个连接执行多个手势：

```python
from hand_gestures import HandGesturePlayer

with HandGesturePlayer() as hand:
    hand.play("open")
    hand.play("pinch")
```
