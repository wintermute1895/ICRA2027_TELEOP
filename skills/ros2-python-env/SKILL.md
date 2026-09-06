---
name: ros2-python-env
description: Run ROS2 Jazzy Python tools such as rosbag exporters and image extractors when Conda or stale colcon overlays hide rclpy.
---

# ROS2 Python environment

Use the bundled wrapper for repository tools that import `rclpy`, especially
rosbag export and RGB keyframe extraction. It clears stale overlay variables
before sourcing ROS2, preventing `/opt/ros/jazzy/setup.bash` from referencing a
deleted workspace `setup.sh`.

```bash
bash skills/ros2-python-env/scripts/run_ros2_python.sh \
  /usr/bin/python3 tools/extract_rosbag_keyframes.py [args...]
```

The wrapper verifies `import rclpy` and fails clearly if the ROS installation
or Python bindings are unavailable. Do not install packages or modify
`third_party/` as part of environment setup. For a different ROS distribution,
set `ROS_SETUP=/opt/ros/<distro>/setup.bash` after verifying that path.
