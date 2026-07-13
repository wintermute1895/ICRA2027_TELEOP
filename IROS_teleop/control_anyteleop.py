import pinocchio as pin
from pinocchio.visualize import MeshcatVisualizer
import meshcat.geometry as g
import numpy as np
import socket
import json
import time
import os
from scipy.spatial.transform import Rotation as R

try:
    from dex_retargeting.retargeting_config import RetargetingConfig
    from dex_retargeting.kinematics_adaptor import MimicJointKinematicAdaptor
except ImportError:
    print("❌ 请确保已安装 dex-retargeting 库")

# ================= 🔧 调试与配置区域 =================

# 1. 镜像开关 (左手控右手 -> True)
MIRROR_LEFT_TO_RIGHT = True 

# 2. 👍 大拇指专属修正 (核心修改区域)
# 现象：方向反了 + 摆动反了 -> 通常意味着绕某个轴转了 180度
# 尝试方案 A: 绕 Z 轴旋转 180 度 (最常见) -> [0, 0, 180]
# 尝试方案 B: 绕 Y 轴旋转 180 度 -> [0, 180, 0]
# 尝试方案 C: 绕 X 轴旋转 180 度 -> [180, 0, 0]
# 请依次尝试这三个值，直到大拇指正常
THUMB_ROTATION_EULER = [0, 0, 180] 

# 大拇指额外偏移 (如果大拇指缩在手心里，往外拉一点)
THUMB_OFFSET = [0.03, 0.0, 0.0] 

# 3. 响应参数
RETARGETING_CONFIG_PARAMS = {
    "norm_delta": 3e-3,
    "low_pass_alpha": 0.15
}

# 4. 路径与关节定义
HAND_URDF = "/home/ilex/Dev/IROS_teleop/config/l10/right/linkerhand_l10_right.urdf"
HAND_PKG_DIR = "/home/ilex/Dev/IROS_teleop/config/l10/right"

ROBOT_TIP_LINKS = ["thumb_distal", "index_distal", "middle_distal", "ring_distal", "pinky_distal"]
# 对应 MediaPipe 的关键点索引: 拇指(4), 食指(8), 中指(12), 无名指(16), 小指(20)
MP_TIP_INDICES = [4, 8, 12, 16, 20] 
TARGET_JOINT_NAMES = [
    "thumb_cmc_roll", "thumb_cmc_yaw", "thumb_cmc_pitch",
    "index_mcp_roll", "index_mcp_pitch",
    "middle_mcp_pitch", 
    "ring_mcp_roll", "ring_mcp_pitch",
    "pinky_mcp_roll", "pinky_mcp_pitch"
]
ROBOT_PALM_LENGTH = 0.09 
OPERATOR2MANO_RIGHT = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]])

class ThumbFixController:
    def __init__(self):
        print(f"🚀 启动大拇指特调控制器...")
        print(f"🔧 大拇指修正旋转: {THUMB_ROTATION_EULER}")
        
        # 1. 加载模型
        self.robot = pin.RobotWrapper.BuildFromURDF(HAND_URDF, package_dirs=[HAND_PKG_DIR])
        self.model, self.data = self.robot.model, self.robot.data
        
        # 2. 配置优化器
        config_dict = {
            "type": "position",
            "urdf_path": HAND_URDF,
            "target_joint_names": TARGET_JOINT_NAMES,
            "target_link_names": ROBOT_TIP_LINKS,
            "target_link_human_indices": np.arange(5),
            "scaling_factor": 1.0, 
            "huber_delta": 2e-2,
            "normal_delta": RETARGETING_CONFIG_PARAMS["norm_delta"], 
            "low_pass_alpha": RETARGETING_CONFIG_PARAMS["low_pass_alpha"] 
        }
        self.retargeting = RetargetingConfig.from_dict(config_dict).build()
        self._inject_mimic_adaptor()
        
        # 3. 计算大拇指修正矩阵
        self.thumb_rot_mat = R.from_euler('xyz', THUMB_ROTATION_EULER, degrees=True).as_matrix()

        # 4. 可视化
        self.viz = MeshcatVisualizer(self.model, self.robot.collision_model, self.robot.visual_model)
        self.viz.initViewer(open=True)
        self.viz.loadViewerModel()
        
        # 调试球体
        colors = [0xff0000, 0x00ff00, 0x00ff00, 0x00ff00, 0x00ff00] # 拇指红球，其他绿球
        for i in range(5):
            self.viz.viewer[f"target_{i}"].set_object(g.Sphere(0.01), g.MeshLambertMaterial(color=colors[i]))
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 5005))
        self.sock.setblocking(False)

    def _inject_mimic_adaptor(self):
        # Linker Hand 关节联动参数
        mimic_rules = [
            ("thumb_cmc_pitch", "thumb_mcp", 1.3898, 0), ("thumb_cmc_pitch", "thumb_ip", 1.508, 0),
            ("index_mcp_pitch", "index_pip", 1.3, 0), ("index_mcp_pitch", "index_dip", 0.4616, 0),
            ("middle_mcp_pitch", "middle_pip", 1.2462, 0), ("middle_mcp_pitch", "middle_dip", 0.4616, 0),
            ("ring_mcp_pitch", "ring_pip", 1.2462, 0), ("ring_mcp_pitch", "ring_dip", 0.4616, 0),
            ("pinky_mcp_pitch", "pinky_pip", 1.2462, 0), ("pinky_mcp_pitch", "pinky_dip", 0.4616, 0),
        ]
        source, mimic, mul, off = zip(*mimic_rules)
        adaptor = MimicJointKinematicAdaptor(
            self.retargeting.optimizer.robot, TARGET_JOINT_NAMES, list(source), list(mimic), list(mul), list(off)
        )
        self.retargeting.optimizer.set_kinematic_adaptor(adaptor)

    def compute_canonical_frame(self, kp):
        wrist, index_mcp, middle_mcp = kp[0], kp[5], kp[9]
        vec_palm = middle_mcp - wrist
        vec_side = index_mcp - wrist
        y_axis = vec_palm / np.linalg.norm(vec_palm)
        z_axis = np.cross(vec_side, y_axis)
        z_axis /= np.linalg.norm(z_axis)
        x_axis = np.cross(y_axis, z_axis)
        return np.stack([x_axis, y_axis, z_axis], axis=1)

    def run(self):
        print("✅ 运行中。请注意观察大拇指（红球）的位置。")
        while True:
            try:
                data, _ = self.sock.recvfrom(65535)
                kp = np.array(json.loads(data.decode())["hand_keypoints_21"])
            except: time.sleep(0.001); continue

            # 1. 镜像处理
            if MIRROR_LEFT_TO_RIGHT:
                kp[:, 0] = -kp[:, 0]

            # 2. 尺度锁定
            human_palm_len = np.linalg.norm(kp[9] - kp[0])
            scale = ROBOT_PALM_LENGTH / human_palm_len if human_palm_len > 0 else 1.0
            
            # 3. 姿态标准化 (计算相对于手腕的坐标)
            rot_mat = self.compute_canonical_frame(kp)
            kp_centered = kp - kp[0]
            kp_aligned = kp_centered @ rot_mat 
            kp_scaled = kp_aligned * scale
            
            # 4. 提取原始目标向量
            target = kp_scaled[MP_TIP_INDICES]
            target = target @ OPERATOR2MANO_RIGHT.T
            
            # ================= 👍 大拇指专属修正区域 =================
            # 这里的 target[0] 是大拇指，target[1:] 是其他四指
            
            # A. 应用旋转修正 (只针对大拇指)
            target[0] = target[0] @ self.thumb_rot_mat.T
            
            # B. 应用额外偏移 (把大拇指拉出来)
            target[0] += np.array(THUMB_OFFSET)
            
            # 其他手指的基础偏移
            target[1:] += np.tile([0.0, 0.0, -0.015], (4, 1))
            # ========================================================

            # 5. 重定向解算
            try:
                retarget_qpos = self.retargeting.retarget(target)
                self.viz.display(retarget_qpos)
                
                # 可视化目标点
                for i in range(5):
                    self.viz.viewer[f"target_{i}"].set_transform(pin.SE3(np.eye(3), target[i]).homogeneous)
            except Exception as e:
                pass

if __name__ == "__main__":
    ThumbFixController().run()