"""
LBot Teleoperation Launch File
遥操作一键启动文件

启动顺序:
1. lbot_driver (从臂/真实机械臂) - 根据配置文件自动启动多个
2. linkerta (主臂/遥操臂)  
3. teleop_bridge (桥接节点)

配置说明:
- 所有从臂配置集中在 config/teleop_config.yaml 的 slave_arm_ips 中
- 只需修改 IP 列表即可实现一控一、一控多
"""

import os
import yaml
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # 获取包路径
    lbot_driver_dir = get_package_share_directory('lbot_driver')
    linkerta_dir = get_package_share_directory('linkerta')
    lbot_teleop_dir = get_package_share_directory('lbot_teleop')
    
    # 配置文件路径
    teleop_config = os.path.join(lbot_teleop_dir, 'config', 'teleop_config.yaml')
    lbot_driver_config = os.path.join(lbot_driver_dir, 'config', 'lbot_config.yaml')
    
    # 读取配置文件获取从臂 IP 列表
    with open(teleop_config, 'r') as f:
        config = yaml.safe_load(f)
    
    slave_arm_ips = config.get('slave_arm_ips', ['192.168.10.21'])
    teleop_bridge_params = config.get('teleop_bridge_node', {}).get('ros__parameters', {})
    
    # 自动生成命名空间列表: robot1, robot2, robot3...
    slave_namespaces = [f"robot{i+1}" for i in range(len(slave_arm_ips))]
    
    # 打印配置信息
    print(f"[teleop.launch.py] 从臂配置:")
    for i, (ns, ip) in enumerate(zip(slave_namespaces, slave_arm_ips)):
        print(f"  - {ns}: {ip}")

    # 1. 启动 lbot_driver (从臂) - 根据 IP 列表动态创建
    driver_nodes = []
    for namespace, arm_ip in zip(slave_namespaces, slave_arm_ips):
        driver_node = Node(
            package='lbot_driver',
            executable='lbot_driver',
            namespace=namespace,
            parameters=[
                lbot_driver_config,
                {"arm_ip": arm_ip}
            ],
            output='screen',
            emulate_tty=True,
        )
        driver_nodes.append(driver_node)
    
    # 2. 启动 linkerta (主臂) - 延迟1秒
    linkerta_launch = TimerAction(
        period=1.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(linkerta_dir, 'launch', 'run.launch.py')
                )
            )
        ]
    )
    
    # 3. 启动 teleop_bridge (桥接节点) - 延迟2秒
    teleop_bridge_node = Node(
        package='lbot_teleop',
        executable='teleop_bridge_node',
        name='teleop_bridge_node',
        output='screen',
        parameters=[
            teleop_bridge_params,
            {"slave_namespaces": slave_namespaces}  # 自动生成的命名空间列表
        ]
    )

    teleop_bridge_launch = TimerAction(
        period=2.0,
        actions=[teleop_bridge_node]
    )
    
    return LaunchDescription([
        *driver_nodes,          # 所有从臂驱动节点
        linkerta_launch,        # 主臂节点
        teleop_bridge_launch,   # 桥接节点
    ])
