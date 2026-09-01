"""Simulation-only command mirror; it intentionally never starts lbot_driver."""
import os
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    root = os.path.abspath(os.path.join(get_package_share_directory("sim_robot_driver"), "../../../../.."))
    sim_share = get_package_share_directory("sim_robot_driver")
    bridge_share = get_package_share_directory("teleop_control_bridge")
    config_path = os.path.join(bridge_share, "config", "hardware_teleop.yaml")
    with open(config_path, encoding="utf-8") as stream:
        bridge_params = yaml.safe_load(stream)["joint_mapping_bridge_node"]["ros__parameters"]
    return LaunchDescription([
        # No robot model is selected by default. The previous O2-derived
        # sensorized model was removed because its shoulder mount was at z=0.
        DeclareLaunchArgument("model_path", default_value=""),
        DeclareLaunchArgument("render", default_value="true"),
        DeclareLaunchArgument("input_mode", default_value="follow_joint"),
        DeclareLaunchArgument("command_namespace", default_value="/robot1"),
        DeclareLaunchArgument("publish_hands", default_value="true"),
        DeclareLaunchArgument("left_hand_model", default_value="L10"),
        DeclareLaunchArgument("right_hand_model", default_value="L10"),
        DeclareLaunchArgument("keyboard", default_value="true"),
        DeclareLaunchArgument("mujoco_python", default_value="/home/ilex/miniforge3/envs/mpc_env/bin/python"),
        Node(package="teleop_control_bridge", executable="joint_mapping_bridge_node", output="screen", parameters=[
            bridge_params,
            {"slave_namespaces": ["robot1"], "armed": True, "require_first_move_service": False},
        ]),

        # The MuJoCo process deliberately uses the dedicated Python 3.10 environment.
        # It has both rclpy and mujoco; hardware nodes retain the ordinary ROS2 runtime.
        ExecuteProcess(cmd=[
            LaunchConfiguration("mujoco_python"),
            os.path.join(sim_share, "../../lib/sim_robot_driver/mujoco_command_mirror"),
            "--ros-args", "-r", "__ns:=/sim/robot1",
            "-p", ["model_path:=", LaunchConfiguration("model_path")],
            "-p", ["render:=", LaunchConfiguration("render")],
            "-p", ["input_mode:=", LaunchConfiguration("input_mode")],
            "-p", ["command_namespace:=", LaunchConfiguration("command_namespace")],
            "-p", ["publish_hands:=", LaunchConfiguration("publish_hands")],
            "-p", ["left_hand_model:=", LaunchConfiguration("left_hand_model")],
            "-p", ["right_hand_model:=", LaunchConfiguration("right_hand_model")],
        ], output="screen"),
        Node(package="sim_robot_driver", executable="keyboard_master", output="screen", condition=IfCondition(LaunchConfiguration("keyboard")), parameters=[{
            "command_namespace": LaunchConfiguration("command_namespace"),
            "left_hand_model": LaunchConfiguration("left_hand_model"),
            "right_hand_model": LaunchConfiguration("right_hand_model"),
        }]),
    ])
