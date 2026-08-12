#!/usr/bin/env python3
"""Mirror shared post-mapping commands into a MuJoCo kinematic simulation."""
from __future__ import annotations

import math
from array import array
from pathlib import Path
from typing import Dict, List, Optional

import rclpy
from rclpy.node import Node
import numpy as np
from sensor_msgs.msg import CameraInfo, Image, JointState
from lbot_arm_interfaces.msg import FollowJoint, VendorArmCommand

ARM_JOINTS = {
    "left": ["Left_Shoulder_Pitch_Joint", "Left_Shoulder_Roll_Joint", "Left_Shoulder_Yaw_Joint", "Left_Elbow_Pitch_Joint", "Left_Wrist_Yaw_Joint", "Left_Wrist_Roll_Joint", "Left_Wrist_Pitch_Joint"],
    "right": ["Right_Shoulder_Pitch_Joint", "Right_Shoulder_Roll_Joint", "Right_Shoulder_Yaw_Joint", "Right_Elbow_Pitch_Joint", "Right_Wrist_Yaw_Joint", "Right_Wrist_Roll_Joint", "Right_Wrist_Pitch_Joint"],
}

# The official LinkerHand SDK publishes 0..255 actuator positions in this
# exact order. The L10 model has 20 visual joints; the map below identifies
# the directly actuated joints. Distal flexion is a documented visual coupling
# approximation in _apply_hand_command, not a claim about the hardware linkage.
HAND_CHANNELS = {
    "O6": [
        "thumb_cmc_pitch", "thumb_cmc_yaw", "index_mcp_pitch",
        "middle_mcp_pitch", "ring_mcp_pitch", "pinky_mcp_pitch",
    ],
    "L10": [
        "thumb_cmc_pitch", "thumb_cmc_yaw", "index_mcp_pitch",
        "middle_mcp_pitch", "ring_mcp_pitch", "pinky_mcp_pitch",
        "index_mcp_roll", "ring_mcp_roll", "pinky_mcp_roll", "thumb_cmc_roll",
    ],
}
HAND_PRIMARY_JOINTS = {
    channel: channel for channel in HAND_CHANNELS["L10"]
}
HAND_FLEXION_COUPLINGS = {
    "index_mcp_pitch": ("index_pip", "index_dip"),
    "middle_mcp_pitch": ("middle_pip", "middle_dip"),
    "ring_mcp_pitch": ("ring_pip", "ring_dip"),
    "pinky_mcp_pitch": ("pinky_pip", "pinky_dip"),
    "thumb_cmc_pitch": ("thumb_mcp", "thumb_ip"),
}


class MujocoCommandMirror(Node):
    """Ideal command mirror: no second mapping/filter/safety layer or SDK call."""
    def __init__(self) -> None:
        super().__init__("mujoco_command_mirror")
        self.declare_parameter("command_namespace", "/robot1")
        self.declare_parameter("input_mode", "vendor_command")
        self.declare_parameter("model_path", "")
        self.declare_parameter("render", True)
        self.declare_parameter("publish_rate_hz", 100.0)
        self.declare_parameter("publish_cameras", True)
        self.declare_parameter("camera_publish_rate_hz", 30.0)
        self.declare_parameter("camera_namespace", "/sim/camera")
        self.declare_parameter("publish_hands", True)
        self.declare_parameter("left_hand_model", "L10")
        self.declare_parameter("right_hand_model", "L10")
        self.command_namespace = str(self.get_parameter("command_namespace").value).rstrip("/")
        self.input_mode = str(self.get_parameter("input_mode").value)
        self.render = bool(self.get_parameter("render").value)
        rate_hz = float(self.get_parameter("publish_rate_hz").value)
        self.publish_cameras = bool(self.get_parameter("publish_cameras").value)
        self.camera_rate_hz = float(self.get_parameter("camera_publish_rate_hz").value)
        self.camera_namespace = str(self.get_parameter("camera_namespace").value).rstrip("/")
        self.publish_hands = bool(self.get_parameter("publish_hands").value)
        self.hand_models = {
            "left": str(self.get_parameter("left_hand_model").value).upper(),
            "right": str(self.get_parameter("right_hand_model").value).upper(),
        }
        if self.input_mode not in {"vendor_command", "follow_joint"}:
            raise ValueError("input_mode must be vendor_command or follow_joint")
        if rate_hz <= 0.0:
            raise ValueError("publish_rate_hz must be positive")
        if any(model not in HAND_CHANNELS for model in self.hand_models.values()):
            raise ValueError("hand model must be O6 or L10")
        self.position: Dict[str, List[float]] = {arm: [0.0] * 7 for arm in ARM_JOINTS}
        self.move_start = {arm: [0.0] * 7 for arm in ARM_JOINTS}
        self.move_target = {arm: [0.0] * 7 for arm in ARM_JOINTS}
        self.move_started_ns = {arm: 0 for arm in ARM_JOINTS}
        self.move_duration_s = {arm: 0.0 for arm in ARM_JOINTS}
        self.state_publishers = {arm: self.create_publisher(JointState, f"{arm}_arm/joint_states", 10) for arm in ARM_JOINTS}
        self.hand_state_publishers = {
            arm: self.create_publisher(JointState, f"{arm}_hand/joint_states", 10)
            for arm in ARM_JOINTS
        }
        self.hand_model_state_publishers = {
            arm: self.create_publisher(JointState, f"{arm}_hand/model_joint_states", 10)
            for arm in ARM_JOINTS
        }
        self.hand_commands = {
            arm: [0.0] * len(HAND_CHANNELS[self.hand_models[arm]]) for arm in ARM_JOINTS
        }
        self.mj_model = self.mj_data = self.viewer = None
        self.mujoco = None
        self.camera_renderer = None
        self.camera_publishers = {}
        self.camera_info_publishers = {}
        self.last_camera_publish_ns = 0
        self.qpos_addresses: Dict[str, int] = {}
        self._load_mujoco()
        if self.input_mode == "vendor_command":
            self.input_subscriptions = [self.create_subscription(VendorArmCommand, f"{self.command_namespace}/{arm}_arm/vendor_command", lambda msg, a=arm: self.vendor_callback(a, msg), 50) for arm in ARM_JOINTS]
        else:
            self.input_subscriptions = [self.create_subscription(FollowJoint, f"{self.command_namespace}/{arm}_arm/joint_follow", lambda msg, a=arm: self.follow_callback(a, msg), 50) for arm in ARM_JOINTS]
        self.hand_subscriptions = []
        if self.publish_hands:
            self.hand_subscriptions = [
                self.create_subscription(
                    JointState, f"{self.command_namespace}/{arm}_hand/control_cmd",
                    lambda msg, a=arm: self.hand_callback(a, msg), 20,
                )
                for arm in ARM_JOINTS
            ]
        self.timer = self.create_timer(1.0 / rate_hz, self.tick)
        self.get_logger().info(
            f"simulation mirror ready: input={self.input_mode}, commands={self.command_namespace}, "
            f"states={self.get_namespace()}, hands={self.hand_models} (no SDK/network calls)"
        )

    def _load_mujoco(self) -> None:
        path_text = str(self.get_parameter("model_path").value)
        if not path_text:
            self.get_logger().warn("model_path empty: publishing mirrored joint state without MuJoCo rendering")
            return
        model_path = Path(path_text).expanduser().resolve()
        if not model_path.is_file():
            raise FileNotFoundError(f"MuJoCo URDF/XML not found: {model_path}")
        try:
            import mujoco
            import mujoco.viewer
        except ImportError as exc:
            raise RuntimeError("MuJoCo Python package is required when model_path is set") from exc
        self.mujoco = mujoco
        self.mj_model = mujoco.MjModel.from_xml_path(str(model_path))
        self.mj_data = mujoco.MjData(self.mj_model)
        for names in ARM_JOINTS.values():
            for name in names:
                joint_id = mujoco.mj_name2id(self.mj_model, mujoco.mjtObj.mjOBJ_JOINT, name)
                if joint_id < 0:
                    raise RuntimeError(f"MuJoCo model missing controller joint: {name}")
                self.qpos_addresses[name] = int(self.mj_model.jnt_qposadr[joint_id])
        if self.publish_hands:
            for arm in ARM_JOINTS:
                for channel in HAND_CHANNELS["L10"]:
                    name = f"{arm.title()}_Hand_{HAND_PRIMARY_JOINTS[channel]}"
                    joint_id = mujoco.mj_name2id(self.mj_model, mujoco.mjtObj.mjOBJ_JOINT, name)
                    if joint_id < 0:
                        raise RuntimeError(f"MuJoCo model missing hand joint: {name}")
                    self.qpos_addresses[name] = int(self.mj_model.jnt_qposadr[joint_id])
                for coupled in HAND_FLEXION_COUPLINGS.values():
                    for suffix in coupled:
                        name = f"{arm.title()}_Hand_{suffix}"
                        joint_id = mujoco.mj_name2id(self.mj_model, mujoco.mjtObj.mjOBJ_JOINT, name)
                        if joint_id < 0:
                            raise RuntimeError(f"MuJoCo model missing hand joint: {name}")
                        self.qpos_addresses[name] = int(self.mj_model.jnt_qposadr[joint_id])
        if self.render:
            self.viewer = mujoco.viewer.launch_passive(self.mj_model, self.mj_data)
        if self.publish_cameras:
            if self.camera_rate_hz <= 0.0:
                raise ValueError("camera_publish_rate_hz must be positive")
            self.camera_renderer = mujoco.Renderer(self.mj_model, height=480, width=640)
            camera_topics = {
                "head_d435i_rgb": "camera",
                "left_wrist_d405_rgb": "left_wrist",
                "right_wrist_d405_rgb": "right_wrist",
            }
            for camera_name, topic_name in camera_topics.items():
                prefix = f"{self.camera_namespace}/{topic_name}"
                self.camera_publishers[camera_name] = (
                    self.create_publisher(Image, f"{prefix}/color/image_raw", 5),
                    self.create_publisher(Image, f"{prefix}/aligned_depth_to_color/image_raw", 5),
                )
                self.camera_info_publishers[camera_name] = (
                    self.create_publisher(CameraInfo, f"{prefix}/color/camera_info", 5),
                    self.create_publisher(CameraInfo, f"{prefix}/depth/camera_info", 5),
                )
            self.get_logger().info(f"simulation cameras enabled: namespace={self.camera_namespace}, rate={self.camera_rate_hz:.1f}Hz")

    @staticmethod
    def _valid(values: List[float]) -> bool:
        return len(values) == 7 and all(math.isfinite(value) for value in values)

    def follow_callback(self, arm: str, msg: FollowJoint) -> None:
        values = [float(value) for value in msg.joints]
        if not self._valid(values):
            self.get_logger().error(f"{arm} FollowJoint rejected: expected 7 finite radians")
            return
        # Same already-filtered/mapped/safety-approved payload lbot_driver would receive.
        self.position[arm], self.move_duration_s[arm] = values, 0.0

    def hand_callback(self, arm: str, msg: JointState) -> None:
        expected = len(HAND_CHANNELS[self.hand_models[arm]])
        values = [float(value) for value in msg.position]
        if len(values) != expected or not all(math.isfinite(value) and 0.0 <= value <= 255.0 for value in values):
            self.get_logger().error(
                f"{arm} {self.hand_models[arm]} hand command rejected: expected {expected} finite values in [0,255]"
            )
            return
        self.hand_commands[arm] = values

    def vendor_callback(self, subscribed_arm: str, msg: VendorArmCommand) -> None:
        arm, values = str(msg.arm), [float(value) for value in msg.joints_rad]
        if arm != subscribed_arm or arm not in ARM_JOINTS or not self._valid(values):
            self.get_logger().error("VendorArmCommand rejected: invalid arm or joint vector")
            return
        if msg.mode == VendorArmCommand.MODE_FOLLOW:
            self.position[arm], self.move_duration_s[arm] = values, 0.0
        elif msg.mode == VendorArmCommand.MODE_MOVEJ:
            speed = float(msg.speed_rad_s)
            if not math.isfinite(speed) or speed <= 0.0:
                self.get_logger().error(f"{arm} MoveJ rejected: speed must be positive")
                return
            self.move_start[arm], self.move_target[arm] = self.position[arm].copy(), values
            self.move_started_ns[arm] = self.get_clock().now().nanoseconds
            self.move_duration_s[arm] = max(abs(a - b) for a, b in zip(self.move_start[arm], values)) / speed
        else:
            self.get_logger().error(f"{arm} VendorArmCommand rejected: unknown mode {msg.mode}")

    def tick(self) -> None:
        now_ns = self.get_clock().now().nanoseconds
        for arm, names in ARM_JOINTS.items():
            duration = self.move_duration_s[arm]
            if duration > 0.0:
                t = min(1.0, max(0.0, (now_ns - self.move_started_ns[arm]) / 1e9 / duration))
                eased = t * t * (3.0 - 2.0 * t)  # visual interpolation, not a vendor dynamics claim
                self.position[arm] = [a + (b - a) * eased for a, b in zip(self.move_start[arm], self.move_target[arm])]
                if t >= 1.0:
                    self.move_duration_s[arm] = 0.0
            state = JointState()
            state.header.stamp, state.header.frame_id = self.get_clock().now().to_msg(), "base_link"
            state.name, state.position = names, self.position[arm]
            self.state_publishers[arm].publish(state)
        self._sync_mujoco()
        if self.publish_hands:
            for arm in ARM_JOINTS:
                self._publish_hand_state(arm)
        self._publish_cameras_if_due()

    def _joint_range(self, name: str) -> tuple[float, float]:
        joint_id = self.mujoco.mj_name2id(self.mj_model, self.mujoco.mjtObj.mjOBJ_JOINT, name)
        return float(self.mj_model.jnt_range[joint_id][0]), float(self.mj_model.jnt_range[joint_id][1])

    def _set_normalized_joint(self, name: str, normalized: float) -> None:
        lower, upper = self._joint_range(name)
        self.mj_data.qpos[self.qpos_addresses[name]] = lower + (upper - lower) * normalized

    def _apply_hand_command(self, arm: str) -> None:
        model = self.hand_models[arm]
        values = self.hand_commands[arm]
        prefix = f"{arm.title()}_Hand_"
        normalized_by_channel = {
            channel: min(1.0, max(0.0, value / 255.0))
            for channel, value in zip(HAND_CHANNELS[model], values)
        }
        for channel, normalized in normalized_by_channel.items():
            self._set_normalized_joint(prefix + HAND_PRIMARY_JOINTS[channel], normalized)
        for channel, (pip, dip) in HAND_FLEXION_COUPLINGS.items():
            if channel not in normalized_by_channel:
                continue
            normalized = normalized_by_channel[channel]
            self._set_normalized_joint(prefix + pip, normalized * 0.75)
            self._set_normalized_joint(prefix + dip, normalized * 0.55)

    def _publish_hand_state(self, arm: str) -> None:
        model = self.hand_models[arm]
        channel_names = HAND_CHANNELS[model]
        state = JointState()
        state.header.stamp, state.header.frame_id = self.get_clock().now().to_msg(), "base_link"
        state.name, state.position = channel_names, self.hand_commands[arm]
        self.hand_state_publishers[arm].publish(state)
        if self.mj_model is not None:
            model_state = JointState()
            model_state.header = state.header
            model_state.name = [f"{arm.title()}_Hand_{channel}" for channel in HAND_CHANNELS["L10"]]
            model_state.position = [float(self.mj_data.qpos[self.qpos_addresses[name]]) for name in model_state.name]
            self.hand_model_state_publishers[arm].publish(model_state)

    def _publish_cameras_if_due(self) -> None:
        if self.camera_renderer is None or not self.camera_publishers:
            return
        now_ns = self.get_clock().now().nanoseconds
        if self.last_camera_publish_ns and now_ns - self.last_camera_publish_ns < int(1e9 / self.camera_rate_hz):
            return
        self.last_camera_publish_ns = now_ns
        stamp = self.get_clock().now().to_msg()
        for camera_name, (rgb_pub, depth_pub) in self.camera_publishers.items():
            self.camera_renderer.update_scene(self.mj_data, camera=camera_name)
            rgb = np.asarray(self.camera_renderer.render(), dtype=np.uint8)
            self.camera_renderer.enable_depth_rendering()
            self.camera_renderer.update_scene(self.mj_data, camera=camera_name)
            depth_m = np.asarray(self.camera_renderer.render(), dtype=np.float32)
            self.camera_renderer.disable_depth_rendering()
            height, width = rgb.shape[:2]
            rgb_msg = Image()
            rgb_msg.header.stamp = stamp
            rgb_msg.header.frame_id = camera_name
            rgb_msg.height, rgb_msg.width = height, width
            rgb_msg.encoding, rgb_msg.is_bigendian = "rgb8", 0
            # ROS2 generated byte sequences accept array('B') without the
            # per-element Python validation cost of list(rgb.tobytes()).
            rgb_msg.step, rgb_msg.data = width * 3, array("B", rgb.tobytes())
            depth_msg = Image()
            depth_msg.header.stamp = stamp
            depth_msg.header.frame_id = camera_name
            depth_msg.height, depth_msg.width = height, width
            depth_msg.encoding, depth_msg.is_bigendian = "16UC1", 0
            depth_mm = np.clip(np.nan_to_num(depth_m, nan=0.0, posinf=0.0, neginf=0.0) * 1000.0, 0, 65535).astype(np.uint16)
            depth_msg.step, depth_msg.data = width * 2, array("B", depth_mm.tobytes())
            info = CameraInfo()
            info.header.stamp, info.header.frame_id = stamp, camera_name
            info.height, info.width = height, width
            camera_id = self.mujoco.mj_name2id(self.mj_model, self.mujoco.mjtObj.mjOBJ_CAMERA, camera_name)
            if camera_id < 0:
                self.get_logger().error(f"camera missing from MuJoCo model: {camera_name}")
                continue
            fy = height / (2.0 * math.tan(math.radians(float(self.mj_model.cam_fovy[camera_id])) / 2.0))
            fx = fy * width / height
            info.k = [fx, 0.0, (width - 1) / 2.0, 0.0, fy, (height - 1) / 2.0, 0.0, 0.0, 1.0]
            info.p = [fx, 0.0, (width - 1) / 2.0, 0.0, 0.0, fy, (height - 1) / 2.0, 0.0, 0.0, 0.0, 1.0, 0.0]
            rgb_pub.publish(rgb_msg); depth_pub.publish(depth_msg)
            self.camera_info_publishers[camera_name][0].publish(info)
            self.camera_info_publishers[camera_name][1].publish(info)

    def _sync_mujoco(self) -> None:
        if self.mj_model is None:
            return
        for arm, names in ARM_JOINTS.items():
            for name, value in zip(names, self.position[arm]):
                self.mj_data.qpos[self.qpos_addresses[name]] = value
        if self.publish_hands:
            for arm in ARM_JOINTS:
                self._apply_hand_command(arm)
        self.mujoco.mj_forward(self.mj_model, self.mj_data)
        if self.viewer is not None:
            self.viewer.sync()

    def destroy_node(self) -> bool:
        if self.viewer is not None:
            self.viewer.close()
        if self.camera_renderer is not None:
            self.camera_renderer.close()
        return super().destroy_node()


def main() -> None:
    rclpy.init(); node: Optional[MujocoCommandMirror] = None
    try:
        node = MujocoCommandMirror(); rclpy.spin(node)
    finally:
        if node is not None: node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
