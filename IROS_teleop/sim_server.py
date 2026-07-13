import numpy as np
import pinocchio as pin
import pink
from pink import solve_ik
from pink.tasks import FrameTask, PostureTask
from pinocchio.visualize import MeshcatVisualizer
import meshcat.geometry as g
import meshcat.transformations as tf
import mediapipe as mp
import cv2
import sys
import os
import time

# ================= 🔧 1. 核心配置 (根据你的模型修改) =================
# URDF 路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
URDF_PATH = os.path.join(CURRENT_DIR, "config/combined_robot/robot.urdf")
PACKAGE_DIRS = [os.path.join(CURRENT_DIR, "config/combined_robot")]

# 关键 Link 名字 (必须与 URDF 一致!)
LINK_WRIST = "Right_Wrist_Roll_Link"  # 机械臂末端/手掌基座

# 五指指尖 Link 名字 (顺序: 拇指, 食指, 中指, 无名指, 小指)
# ⚠️ 如果名字不对，那根手指就不会动
LINK_FINGERTIPS = [
    "thumb_distal", 
    "index_distal", 
    "middle_distal", 
    "ring_distal", 
    "pinky_distal"
]

# ================= 🔧 2. 操作参数 (手感微调) =================
# 空间映射比例 (Sim2Real Scale)
SCALE_ARM_WS = 1.5   # 手臂工作空间放大倍率 (1.5倍移动速度)
SCALE_HAND_SIZE = 1.2 # 手掌大小修正 (如果你手小，把这个调大)

# 平滑系数 (0.0~1.0, 越小越平滑但延迟高)
SMOOTHING = 0.5 

# 场景物体 (模拟插孔)
HOLE_POS = np.array([0.5, -0.2, 0.4]) 
PEG_LENGTH = 0.15

class AnyTeleopSystem:
    def __init__(self):
        print("🚀 初始化 AnyTeleop 系统...")
        
        # 1. 加载机器人 & 物理引擎
        if not os.path.exists(URDF_PATH):
            print(f"❌ 找不到 URDF: {URDF_PATH}"); sys.exit()
            
        self.robot = pin.RobotWrapper.BuildFromURDF(URDF_PATH, package_dirs=PACKAGE_DIRS, root_joint=None)
        self.model = self.robot.model
        self.data = self.robot.data
        
        # 2. 启动可视化
        self.viz = MeshcatVisualizer(self.model, self.robot.collision_model, self.robot.visual_model)
        self.viz.initViewer(open=True)
        self.viz.loadViewerModel()
        self._init_scene_viz() # 画孔和棍子

        # 3. 初始化 IK 配置 (Pink)
        self.q = pin.neutral(self.model)
        self.configuration = pink.Configuration(self.model, self.data, self.q)
        
        # --- 定义优化任务 (Optimization Tasks) ---
        self.tasks = []
        
        # [Task 1] 手腕追踪 (权重最高)
        self.task_wrist = FrameTask(LINK_WRIST, position_cost=10.0, orientation_cost=1.0)
        self.task_wrist.gain = 5.0 
        self.tasks.append(self.task_wrist)
        
        # [Task 2] 指尖追踪 (AnyTeleop 核心: 将手指几何作为约束)
        self.finger_tasks = []
        for i, tip_name in enumerate(LINK_FINGERTIPS):
            try:
                # 检查 Link 是否存在
                if not self.model.existBodyName(tip_name):
                    print(f"⚠️ 警告: URDF 中找不到 Link '{tip_name}'，跳过该手指")
                    self.finger_tasks.append(None)
                    continue
                    
                # 创建任务: 只追踪位置，权重稍低，允许为了避障稍微牺牲手指精度
                task = FrameTask(tip_name, position_cost=1.0, orientation_cost=0.0)
                task.gain = 5.0
                self.finger_tasks.append(task)
                self.tasks.append(task)
                
                # 可视化目标点 (绿球)
                self.viz.viewer[f'target_{i}'].set_object(g.Sphere(0.015), g.MeshLambertMaterial(color=0x00ff00))
            except Exception as e:
                print(f"❌ 初始化手指 {tip_name} 失败: {e}")

        # [Task 3] 姿态约束 (防止乱扭)
        self.task_posture = PostureTask(cost=0.001)
        self.task_posture.set_target(self.q)
        self.tasks.append(self.task_posture)

        # 4. 视觉模块 (MediaPipe)
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            model_complexity=1, max_num_hands=1, 
            min_detection_confidence=0.7, min_tracking_confidence=0.7)
        self.cap = cv2.VideoCapture(0)

        # 5. 控制状态变量
        self.calibrated = False
        self.clutch_active = False # 离合器状态
        
        # 参考坐标 (Human T0 & Robot T0)
        self.ref_h_wrist = None
        self.ref_r_wrist = None
        
        # 上一帧数据 (用于滤波)
        self.last_target_wrist = None

    def _init_scene_viz(self):
        # 画个孔
        self.viz.viewer['hole'].set_object(g.Cylinder(0.01, 0.03), g.MeshLambertMaterial(color=0xff0000, opacity=0.5))
        T = np.eye(4); T[:3,3] = HOLE_POS; self.viz.viewer['hole'].set_transform(T)
        # 画个棍子 (稍后随手腕更新)
        self.viz.viewer['peg'].set_object(g.Cylinder(PEG_LENGTH, 0.01), g.MeshLambertMaterial(color=0x0000ff))

    def _get_hand_landmarks(self, frame):
        frame.flags.writeable = False
        res = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        return res.multi_hand_landmarks[0] if res.multi_hand_landmarks else None

    def step(self):
        ret, frame = self.cap.read()
        if not ret: return False
        
        # 镜像翻转，符合直觉
        frame = cv2.flip(frame, 1)
        landmarks = self._get_hand_landmarks(frame)
        
        # === 🎮 键盘交互 (模拟 AnyTeleop 的 Clutch) ===
        key = cv2.waitKey(5)
        if key == 27: return False # ESC 退出
        if key == 32: # Space 键: 按下=激活(Clutch Engaged)，松开=暂停
            if not self.clutch_active and landmarks:
                print("🟢 Clutch Engaged (控制激活)")
                self.clutch_active = True
                # 记录这一刻的人手和机器人位置作为基准 (Reset Origin)
                self.ref_h_wrist = np.array([landmarks.landmark[0].x, landmarks.landmark[0].y, landmarks.landmark[0].z])
                self.ref_r_wrist = self.configuration.get_transform_frame_to_world(LINK_WRIST).translation.copy()
        elif key == -1: # 没有按键
             if self.clutch_active:
                print("⚪ Clutch Disengaged (暂停/重置手位)")
                self.clutch_active = False

        # === 核心控制循环 ===
        if landmarks and self.clutch_active:
            # 1. 提取关键点
            # 0: Wrist
            # Fingertips: 4, 8, 12, 16, 20
            lm = landmarks.landmark
            h_wrist = np.array([lm[0].x, lm[0].y, lm[0].z])
            
            # 2. 计算手臂目标 (增量控制)
            # Human Delta
            delta = h_wrist - self.ref_h_wrist
            
            # 坐标系映射 (Camera -> Robot)
            # Cam X(右) -> Robot -Y
            # Cam Y(下) -> Robot -Z
            # Cam Z(深) -> Robot X
            robot_delta = np.array([
                delta[2] * SCALE_ARM_WS,       # 前后
                -(delta[0]) * SCALE_ARM_WS,    # 左右
                -(delta[1]) * SCALE_ARM_WS     # 上下
            ])
            
            target_wrist_pos = self.ref_r_wrist + robot_delta
            
            # [简单平滑滤波]
            if self.last_target_wrist is not None:
                target_wrist_pos = self.last_target_wrist * SMOOTHING + target_wrist_pos * (1.0 - SMOOTHING)
            self.last_target_wrist = target_wrist_pos

            # 设置 IK 目标 (Wrist)
            T_wrist = pin.SE3.Identity()
            T_wrist.translation = target_wrist_pos
            # 这里简单起见，不跟随手腕旋转，只跟随位置 (更稳定)
            # 如果要跟随旋转，需要计算 RPY 并设置 T_wrist.rotation
            self.task_wrist.set_target(T_wrist)

            # 3. 计算手指目标 (Retargeting)
            # 获取当前机器人手腕的位姿矩阵 (用于把相对坐标转为绝对坐标)
            robot_wrist_trans = self.configuration.get_transform_frame_to_world(LINK_WRIST)
            
            tip_indices = [4, 8, 12, 16, 20]
            for i, task in enumerate(self.finger_tasks):
                if task is None: continue
                
                # 人手：指尖相对于手腕的向量
                h_tip = np.array([lm[tip_indices[i]].x, lm[tip_indices[i]].y, lm[tip_indices[i]].z])
                rel_vec_human = h_tip - h_wrist
                
                # 坐标系旋转 (MediaPipe -> Robot Hand)
                # 假设：机器人手掌朝前(X+)，拇指朝上(Z+)，左侧(Y+)
                # 需要根据你的手掌具体安装方向微调这里！
                # 这里的映射是基于常见配置的猜想
                rel_vec_robot = np.array([
                    -rel_vec_human[2], # MP Deep(Z) -> Robot Forward(X)
                    -rel_vec_human[0], # MP Right(X) -> Robot Left(Y)
                    -rel_vec_human[1]  # MP Down(Y)  -> Robot Up(Z)
                ]) * SCALE_HAND_SIZE * 5.0 # 放大系数
                
                # 机器人绝对目标 = 手腕当前位置 + 旋转后的相对向量
                target_tip_pos = robot_wrist_trans.translation + \
                                 robot_wrist_trans.rotation @ rel_vec_robot
                
                # 设置 IK 目标
                task.set_target(pin.SE3(np.eye(3), target_tip_pos))
                
                # 更新绿球位置
                T_viz = np.eye(4); T_viz[:3,3] = target_tip_pos
                self.viz.viewer[f'target_{i}'].set_transform(T_viz)

            # 4. 求解 IK (Optimization)
            dt = 0.03
            vel = solve_ik(self.configuration, self.tasks, dt, solver="quadprog", damping=1e-3)
            self.configuration.integrate_inplace(vel, dt)
            
            # 5. 更新显示
            self.viz.display(self.configuration.q)
            
            # 更新棍子 (跟随手腕)
            wrist_pos = self.configuration.get_transform_frame_to_world(LINK_WRIST).translation
            T_peg = np.eye(4); T_peg[:3,3] = wrist_pos - np.array([0,0,PEG_LENGTH/2])
            # 假设棍子垂直向下
            T_peg[:3,:3] = tf.rotation_matrix(np.pi/2, [1,0,0])[:3,:3]
            self.viz.viewer['peg'].set_transform(T_peg)

        # 状态显示
        status_color = (0, 255, 0) if self.clutch_active else (0, 0, 255)
        status_text = "ACTIVE (Space Down)" if self.clutch_active else "PAUSED (Press Space)"
        cv2.putText(frame, status_text, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)
        cv2.imshow('AnyTeleop View', frame)
        
        return True

if __name__ == "__main__":
    app = AnyTeleopSystem()
    while True:
        if not app.step(): break
    cv2.destroyAllWindows()