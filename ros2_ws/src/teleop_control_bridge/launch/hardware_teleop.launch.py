"""
LBot Teleoperation Launch File
遥操作一键启动文件

启动顺序:
1. lbot_driver (从臂/真实机械臂) - 根据配置文件自动启动多个
2. linkerta (主臂/遥操臂)  
3. teleop_bridge (桥接节点)

配置说明:
- 所有从臂配置集中在 config/hardware_teleop.yaml 的 slave_arm_ips 中
- 只需修改 IP 列表即可实现一控一、一控多
"""

import os
import yaml
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # 获取包路径
    lbot_driver_dir = get_package_share_directory('lbot_driver')
    linkerta_dir = get_package_share_directory('linkerta')
    teleop_control_bridge_dir = get_package_share_directory('teleop_control_bridge')
    
    # 配置文件路径
    teleop_config = os.path.join(teleop_control_bridge_dir, 'config', 'hardware_teleop.yaml')
    lbot_driver_config = os.path.join(lbot_driver_dir, 'config', 'lbot_config.yaml')
    
    # 读取配置文件获取从臂 IP 列表
    with open(teleop_config, 'r') as f:
        config = yaml.safe_load(f)
    
    slave_arm_ips = config.get('slave_arm_ips', ['192.168.10.21'])
    bridge_params = config.get('joint_mapping_bridge_node', {}).get('ros__parameters', {})
    
    # 自动生成命名空间列表: robot1, robot2, robot3...
    slave_namespaces = [f"robot{i+1}" for i in range(len(slave_arm_ips))]
    launch_driver = LaunchConfiguration("launch_driver")
    launch_linkerta = LaunchConfiguration("launch_linkerta")
    enable_left_arm = LaunchConfiguration("enable_left_arm")
    enable_right_arm = LaunchConfiguration("enable_right_arm")
    master_left_topic = LaunchConfiguration("master_left_topic")
    master_right_topic = LaunchConfiguration("master_right_topic")
    
    # 打印配置信息
    print(f"[hardware_teleop.launch.py] 从臂配置:")
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
            condition=IfCondition(launch_driver),
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
            ),
        ],
            condition=IfCondition(launch_linkerta),
    )
    
    # 3. 启动 teleop_bridge (桥接节点) - 延迟2秒
    joint_mapping_bridge_node = Node(
        package='teleop_control_bridge',
        executable='joint_mapping_bridge_node',
        name='joint_mapping_bridge_node',
        output='screen',
        parameters=[
            bridge_params,
            {"slave_namespaces": slave_namespaces},
            {"armed": ParameterValue(LaunchConfiguration("armed"), value_type=bool)},
            {"enable_left_arm": ParameterValue(enable_left_arm, value_type=bool)},
            {"enable_right_arm": ParameterValue(enable_right_arm, value_type=bool)},
            {"master_left_topic": master_left_topic},
            {"master_right_topic": master_right_topic},
            {"initial_movej_mode": LaunchConfiguration("initial_movej_mode")},
            {"first_command_max_delta_rad": ParameterValue(
                LaunchConfiguration("first_command_max_delta_rad"), value_type=float)},
            {"measured_state_max_age_s": ParameterValue(
                LaunchConfiguration("measured_state_max_age_s"), value_type=float)},
        ]
    )

    bridge_launch = TimerAction(
        period=2.0,
        actions=[joint_mapping_bridge_node]
    )
    
    return LaunchDescription([
        DeclareLaunchArgument(
            "launch_driver", default_value="true",
            description="Launch lbot_driver nodes. Set false to reuse an already-running driver.",
        ),
        DeclareLaunchArgument(
            "launch_linkerta", default_value="true",
            description="Launch LinkerTA master-arm node.",
        ),
        DeclareLaunchArgument("armed", default_value="false",
                              description="Explicitly allow commands to reach the robot"),
        DeclareLaunchArgument("enable_left_arm", default_value="true"),
        DeclareLaunchArgument("enable_right_arm", default_value="true"),
        DeclareLaunchArgument("master_left_topic", default_value=str(bridge_params["master_left_topic"])),
        DeclareLaunchArgument("master_right_topic", default_value=str(bridge_params["master_right_topic"])),
        DeclareLaunchArgument(
            "initial_movej_mode", default_value="",
            description="Right-arm startup mode: 'required', 'bypass', or empty for legacy bool behavior"),
        DeclareLaunchArgument(
            "first_command_max_delta_rad", default_value="0.0",
            description="Bypass fail-safe: reject the first model frame farther than this from measured pose"),
        DeclareLaunchArgument(
            "measured_state_max_age_s", default_value="5.0",
            description="Maximum age of cached measured state accepted for startup auditing"),
        *driver_nodes,          # 所有从臂驱动节点
        linkerta_launch,        # 主臂节点
        bridge_launch,          # mapping/filter/safety bridge
    ])
