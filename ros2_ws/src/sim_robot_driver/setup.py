from setuptools import setup

package_name = "sim_robot_driver"
setup(
    name=package_name, version="0.1.0", packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/sim_robot_driver"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", [
            "launch/sim_teleop.launch.py",
            "launch/replay_reference_trajectory.launch.py",
        ]),
    ],
    install_requires=["setuptools"], zip_safe=True,
    maintainer="LinkerRobot", maintainer_email="support@linkerrobot.com",
    description="MuJoCo command mirror for the LinkerBot teleoperation platform.", license="Apache-2.0",
    entry_points={"console_scripts": [
        "mujoco_command_mirror = sim_robot_driver.mujoco_command_mirror:main",
        "keyboard_master = sim_robot_driver.keyboard_master:main",
        "causal_filter_node = sim_robot_driver.causal_filter_node:main",
        "reference_trajectory_replayer = sim_robot_driver.reference_trajectory_replayer:main",
    ]},
)
