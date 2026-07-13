"""
LBot Driver Launch File
从臂驱动启动文件

可以独立使用，也可以被 teleop.launch.py 调用
配置来源: lbot_teleop/config/teleop_config.yaml 的 slave_arm_ips
"""

import os
import yaml
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():

    # 获取配置文件路径
    lbot_driver_dir = get_package_share_directory('lbot_driver')
    base_yaml_file = os.path.join(lbot_driver_dir, 'config', 'lbot_config.yaml')
    
    # 尝试读取统一配置文件
    try:
        lbot_teleop_dir = get_package_share_directory('lbot_teleop')
        teleop_config_file = os.path.join(lbot_teleop_dir, 'config', 'teleop_config.yaml')
        with open(teleop_config_file, 'r') as f:
            config = yaml.safe_load(f)
        slave_arm_ips = config.get('slave_arm_ips', ['192.168.10.21'])
    except Exception as e:
        # 如果找不到 teleop 配置，使用默认值
        print(f"[lbot_start_driver] 未找到 teleop_config.yaml，使用默认配置: {e}")
        slave_arm_ips = ['192.168.10.21']
    
    # 自动生成命名空间: robot1, robot2, robot3...
    nodes = []
    for i, arm_ip in enumerate(slave_arm_ips):
        namespace = f"robot{i+1}"
        print(f"[lbot_start_driver] 启动 {namespace}: {arm_ip}")
        
        driver_node = Node(
            package='lbot_driver',
            executable='lbot_driver',
            namespace=namespace,
            parameters=[
                base_yaml_file,
                {"arm_ip": arm_ip}
            ],
            output='screen',
            emulate_tty=True,
        )
        nodes.append(driver_node)

    return LaunchDescription(nodes)
