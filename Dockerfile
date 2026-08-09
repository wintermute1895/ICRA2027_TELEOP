# syntax=docker/dockerfile:1
FROM ros:humble-ros-base-jammy

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=humble
ENV WORKSPACE=/opt/robot_teleop_platform

ARG BUILD_HTTP_PROXY
ARG BUILD_HTTPS_PROXY
ARG BUILD_ALL_PROXY
ARG BUILD_NO_PROXY

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    can-utils \
    git \
    iproute2 \
    python3-colcon-common-extensions \
    python3-pip \
    python3-yaml \
    ros-humble-image-transport-plugins \
    ros-humble-realsense2-camera \
    ros-humble-rqt-image-view \
    ros-humble-rosbag2-compression-zstd \
    tmux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ${WORKSPACE}
COPY ros2_ws/src ros2_ws/src
RUN source /opt/ros/humble/setup.bash && \
    colcon build --base-paths ros2_ws/src \
      --build-base ros2_ws/build \
      --install-base ros2_ws/install

COPY assets/robots/linker_platform assets/robots/linker_platform
COPY third_party/linkerbot_sdk third_party/linkerbot_sdk
COPY scripts scripts
COPY tools tools
COPY docs docs
COPY requirements-runevidence.txt requirements-runevidence.txt

RUN --network=host \
    HTTP_PROXY="${BUILD_HTTP_PROXY}" \
    HTTPS_PROXY="${BUILD_HTTPS_PROXY}" \
    ALL_PROXY="${BUILD_ALL_PROXY}" \
    NO_PROXY="${BUILD_NO_PROXY}" \
    python3 -m pip install --no-cache-dir \
    -r requirements-runevidence.txt

COPY docker/entrypoint.sh /usr/local/bin/robot-teleop-entrypoint
RUN chmod +x /usr/local/bin/robot-teleop-entrypoint

ENTRYPOINT ["/usr/local/bin/robot-teleop-entrypoint"]
CMD ["bash"]
