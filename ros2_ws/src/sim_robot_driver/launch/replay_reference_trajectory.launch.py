"""Launch the MuJoCo mirror and a fixed reference replay in an isolated namespace."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory("sim_robot_driver")
    return LaunchDescription([
        DeclareLaunchArgument("trajectory_csv"),
        DeclareLaunchArgument("model_path"),
        DeclareLaunchArgument("render", default_value="true"),
        DeclareLaunchArgument("mujoco_python", default_value="/home/ilex/miniforge3/envs/mpc_env/bin/python"),
        DeclareLaunchArgument("start_delay_s", default_value="1.0"),
        DeclareLaunchArgument("start_speed_rad_s", default_value="0.05"),
        DeclareLaunchArgument("start_acceleration_rad_s2", default_value="0.05"),
        DeclareLaunchArgument("playback_rate", default_value="1.0"),
        ExecuteProcess(
            cmd=[
                LaunchConfiguration("mujoco_python"),
                os.path.join(package_share, "../../lib/sim_robot_driver/mujoco_command_mirror"),
                "--ros-args", "-r", "__ns:=/sim/robot1",
                "-p", ["model_path:=", LaunchConfiguration("model_path")],
                "-p", ["render:=", LaunchConfiguration("render")],
                "-p", "input_mode:=vendor_command",
                "-p", "command_namespace:=/sim_reference",
                "-p", "publish_hands:=false",
            ],
            output="screen",
        ),
        Node(
            package="sim_robot_driver",
            executable="reference_trajectory_replayer",
            output="screen",
            parameters=[{
                "trajectory_csv": LaunchConfiguration("trajectory_csv"),
                "command_namespace": "/sim_reference",
                "start_delay_s": LaunchConfiguration("start_delay_s"),
                "start_speed_rad_s": LaunchConfiguration("start_speed_rad_s"),
                "start_acceleration_rad_s2": LaunchConfiguration("start_acceleration_rad_s2"),
                "playback_rate": LaunchConfiguration("playback_rate"),
                "loop": False,
            }],
        ),
    ])
