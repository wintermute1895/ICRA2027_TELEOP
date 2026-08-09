FROM ros:humble-ros-base-jammy

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=humble
ENV WORKSPACE=/opt/icra2027_teleop

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
COPY arm_teleop/src arm_teleop/src
RUN source /opt/ros/humble/setup.bash && \
    colcon build --base-paths arm_teleop/src \
      --build-base arm_teleop/build \
      --install-base arm_teleop/install

COPY IROS_teleop IROS_teleop
COPY scripts scripts
COPY tools tools
COPY docs docs
COPY requirements-runevidence.txt requirements-runevidence.txt

RUN python3 -m pip install --no-cache-dir \
    -r requirements-runevidence.txt

COPY docker/entrypoint.sh /usr/local/bin/icra2027-entrypoint
RUN chmod +x /usr/local/bin/icra2027-entrypoint

ENTRYPOINT ["/usr/local/bin/icra2027-entrypoint"]
CMD ["bash"]
