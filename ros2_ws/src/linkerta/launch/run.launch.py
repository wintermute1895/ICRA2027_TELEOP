from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    pkg_dir = get_package_share_directory('linkerta')

    lta_params_file = os.path.join(pkg_dir, 'config', 'lta.yaml')

    return LaunchDescription([
        Node(
            package='linkerta',
            executable='linkerta_node',
            name='linkerta_node',
            output='screen',
            respawn=True,
            respawn_delay=3.0,
            parameters=[
                lta_params_file
            ]
        )
    ])
