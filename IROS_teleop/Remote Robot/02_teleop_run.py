#!/usr/bin/env python3
# 文件名: 02_teleop_run.py
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import math
import sys
import os

try:
    from lbot.lbot_robot import LbotRobot, LbotArm
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from lbot.lbot_robot import LbotRobot, LbotArm

# ================= 用户配置区 (从脚本一获取结果) =================
# 1. 机械臂 IP
ROBOT_IP = "192.168.10.21"

# 2. Topic 名字
TOPIC_NAME = '/right_arm_joint_control'

# 3. 主端索引
MASTER_INDICES = [0, 1, 2, 3, 4, 5, 6] 

# 4. 零位偏置 (请把脚本一算出来的数组粘贴到这里！)
# 例如: [15.2, -10.5, 0.0, ...]
self_offsets_deg = [-0.004119873057300496, 0.001373291053840304, -13.000596788247721, -1.6018310785803116, 0.5993896722450033, -3.2981688975778303, 6.201220512458846]
# 5. 方向修正 (1.0 或 -1.0)
# 如果发现某个关节反向运动，将对应位置改为 -1.0
self_directions = [-1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]
# ============================================================

class TeleopNode(Node):
    def __init__(self):
        super().__init__('teleop_node')
        self.get_logger().info(">>> 正在启动遥操作控制 <<<")

        # 连接
        self.robot = LbotRobot(ROBOT_IP)
        if not self.robot.connect():
            self.get_logger().error("连接失败！")
            sys.exit(1)
        
        # === 核心：使能机械臂 ===
        # 注意：运行到这里机械臂会变硬（进入伺服状态）
        self.get_logger().info("正在使能机械臂 (Enable)...")
        self.robot.enable_arm(LbotArm.RIGHT_ARM, True)
        self.robot.clear_errors() # 清除可能的错误
        
        # 订阅
        self.sub = self.create_subscription(
            JointState, TOPIC_NAME, self.listener_callback, 10
        )
        self.get_logger().info(">>> 系统就绪，开始跟随！注意安全！ <<<")

    def listener_callback(self, msg):
        try:
            target_joints_rad = []
            
            for i, idx in enumerate(MASTER_INDICES):
                if idx >= len(msg.position): continue
                
                # 1. 读取主端
                raw_deg = msg.position[idx]
                
                # 2. 减去偏置 (Offset)
                # 目标 = (主端 - 偏置) * 方向
                target_deg = (raw_deg - self_offsets_deg[i])
                
                # 3. 转弧度并应用方向
                val_rad = math.radians(target_deg) * self_directions[i]
                target_joints_rad.append(val_rad)

            if len(target_joints_rad) == 7:
                # 4. 发送高频跟随指令
                self.robot.joint_follow(LbotArm.RIGHT_ARM, target_joints_rad, follow=True)
            
        except Exception as e:
            self.get_logger().error(f"Error: {e}")

    def destroy_node(self):
        # 退出时尝试失能或仅断开
        self.get_logger().info("正在停止...")
        # self.robot.enable_arm(LbotArm.RIGHT_ARM, False) # 可选：退出时掉使能
        self.robot.disconnect()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = TeleopNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()