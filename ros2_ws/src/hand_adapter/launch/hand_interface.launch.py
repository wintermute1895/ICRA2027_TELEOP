"""Start the safe hand adapter and optionally the official CAN SDK nodes."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    left_model = LaunchConfiguration("left_model")
    right_model = LaunchConfiguration("right_model")
    left_sdk_model = LaunchConfiguration("left_sdk_model")
    right_sdk_model = LaunchConfiguration("right_sdk_model")
    return LaunchDescription([
        DeclareLaunchArgument("robot_namespace", default_value="/robot1"),
        # Physical setup: left hand is L10 and the active right hand is O6.
        # Override explicitly when the hardware assignment changes.
        DeclareLaunchArgument("left_model", default_value="L10"),
        DeclareLaunchArgument("right_model", default_value="O6"),
        DeclareLaunchArgument("left_sdk_model", default_value="L10"),
        DeclareLaunchArgument("right_sdk_model", default_value="O6"),
        DeclareLaunchArgument("left_can", default_value="can0"),
        DeclareLaunchArgument("right_can", default_value="can1"),
        DeclareLaunchArgument("left_touch", default_value="false"),
        DeclareLaunchArgument("right_touch", default_value="false"),
        DeclareLaunchArgument("launch_sdk", default_value="false"),
        # SDK nodes are opt-in per hand. This keeps observation-only launches
        # from opening a CAN device that is not part of the session.
        DeclareLaunchArgument("launch_left_sdk", default_value="false"),
        DeclareLaunchArgument("launch_right_sdk", default_value="false"),
        DeclareLaunchArgument("initialize_pose", default_value="false"),
        DeclareLaunchArgument("allow_sdk_commands", default_value="false"),
        DeclareLaunchArgument("armed", default_value="false"),
        Node(package="hand_adapter", executable="hand_adapter", output="screen", parameters=[{
            "robot_namespace": LaunchConfiguration("robot_namespace"),
            "left_model": left_model,
            "right_model": right_model,
            "armed": LaunchConfiguration("armed"),
        }]),
        Node(package="linker_hand_ros2_sdk", executable="linker_hand_sdk", name="linker_hand_sdk_left", output="screen", condition=IfCondition(LaunchConfiguration("launch_left_sdk")), parameters=[{
            "hand_type": "left", "hand_joint": left_sdk_model, "is_touch": LaunchConfiguration("left_touch"),
            "can": LaunchConfiguration("left_can"), "modbus": "None",
            "initialize_pose": LaunchConfiguration("initialize_pose"),
            "allow_commands": LaunchConfiguration("allow_sdk_commands"),
        }]),
        Node(package="linker_hand_ros2_sdk", executable="linker_hand_sdk", name="linker_hand_sdk_right", output="screen", condition=IfCondition(LaunchConfiguration("launch_right_sdk")), parameters=[{
            "hand_type": "right", "hand_joint": right_sdk_model, "is_touch": LaunchConfiguration("right_touch"),
            "can": LaunchConfiguration("right_can"), "modbus": "None",
            "initialize_pose": LaunchConfiguration("initialize_pose"),
            "allow_commands": LaunchConfiguration("allow_sdk_commands"),
        }]),
    ])
