import launch
import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    """
    启动 lbot_driver + linkerta + joint_bridge
    实现 linkerta 遥操作数据转发到 lbot_driver
    """
    
    # 获取包路径
    lbot_driver_dir = get_package_share_directory('lbot_driver')
    linkerta_dir = get_package_share_directory('linkerta')
    
    # 1. 启动 lbot_driver
    lbot_driver_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(lbot_driver_dir, 'launch', 'lbot_start_driver.launch.py')
        )
    )
    
    # 2. 启动 linkerta (延迟1秒)
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
    
    # 3. 启动 joint_bridge 桥接节点 (延迟2秒)
    joint_bridge_node = TimerAction(
        period=2.0,
        actions=[
            Node(
                package='lbot_demo',
                executable='demo_joint_bridge',
                name='joint_bridge_node',
                output='screen',
                parameters=[
                    {'robot_namespace': 'robot1'},
                    {'follow_mode': True},
                    {'convert_to_radians': True}  # linkerta输出度，转换为弧度
                ]
            )
        ]
    )
    
    return LaunchDescription([
        lbot_driver_launch,
        linkerta_launch,
        joint_bridge_node,
    ])
