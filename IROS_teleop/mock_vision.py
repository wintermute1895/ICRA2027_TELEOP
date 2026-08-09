import socket
import json
import time
import math
import argparse
import numpy as np
from scipy.spatial.transform import Rotation as R

# The receiver consumes MediaPipe's 21 points. Keep this schema identical to
# vision_pose.py so mock and camera input are interchangeable.

def get_rotation_matrix(t):
    # 模拟手腕旋转 (画圈圈)
    angle_y = 0.6 * math.sin(t) 
    angle_x = 0.2 * math.cos(t)
    r = R.from_euler('xyz', [angle_x, angle_y, 0], degrees=False)
    return r.as_matrix().tolist()

def get_finger_trajectory(t):
    """
    生成更真实的五指抓握数据
    """
    # grip: 0 = 张开, 1 = 握拳 (正弦波控制)
    grip = (math.sin(t * 3.0) + 1) / 2
    
    fingers_rel = []
    
    # 定义5根手指的"张开"和"握拳"相对坐标 (相对于手腕)
    # 假设手腕坐标系：X=前方(指尖方向), Y=左方(大拇指侧), Z=上方(手背)
    # 注意：如果你的机械臂坐标系不同，可能需要调整这些数值
    
    for i in range(5):
        # i=0(拇指), 1(食指), 2(中指), 3(无名指), 4(小指)
        
        # === 1. 张开状态 (Open) ===
        # 手指伸长 (X大)，且呈扇形散开 (Y根据i变化)
        spread_y = (i - 2) * 0.03  # 中指在中间，两边散开
        pos_open = np.array([0.15, spread_y, 0.02]) 
        
        # === 2. 握拳状态 (Close) ===
        # 手指缩回 (X小)，聚拢 (Y小)，向下弯曲 (Z负值大)
        close_spread_y = (i - 2) * 0.01 # 聚拢
        pos_close = np.array([0.06, close_spread_y, -0.06])
        
        # === 3. 特殊处理大拇指 (i=0) ===
        if i == 0:
            pos_open = np.array([0.10, 0.08, 0.0])   # 拇指张开在侧面
            pos_close = np.array([0.06, 0.04, -0.04]) # 拇指握在手心
            
        # 线性插值：根据 grip (0~1) 计算当前位置
        current_pos = pos_open * (1 - grip) + pos_close * grip
        fingers_rel.append(current_pos.tolist())
        
    return fingers_rel

def make_hand_keypoints(t):
    """Return a plausible MediaPipe-style 21x3 hand in metres."""
    wrist = np.array([0.0, 0.0, 0.0])
    palm = np.array([
        wrist,
        [0.018, -0.020, 0.0], [0.040, -0.024, 0.0], [0.060, -0.018, 0.0],
        [0.078, -0.005, 0.0],
        [0.020, 0.018, 0.0], [0.045, 0.018, 0.0], [0.070, 0.018, 0.0],
        [0.092, 0.018, 0.0],
        [0.020, 0.050, 0.0], [0.047, 0.050, 0.0], [0.075, 0.050, 0.0],
        [0.102, 0.050, 0.0],
        [0.018, 0.078, 0.0], [0.043, 0.080, 0.0], [0.067, 0.078, 0.0],
        [0.090, 0.075, 0.0],
        [0.010, 0.103, 0.0], [0.032, 0.108, 0.0], [0.055, 0.105, 0.0],
        [0.078, 0.100, 0.0],
    ], dtype=float)
    grip = (math.sin(t * 3.0) + 1.0) / 2.0
    # Curl the finger joints toward the palm while preserving the 21-point
    # indexing expected by the retargeter.
    for tip_start in (8, 12, 16, 20):
        palm[tip_start - 2:tip_start + 1, 0] -= 0.035 * grip
        palm[tip_start - 2:tip_start + 1, 2] -= 0.050 * grip
    palm[1:5, 0] -= 0.020 * grip
    palm[1:5, 2] -= 0.035 * grip
    rot = R.from_euler('xyz', [0.2 * math.cos(t), 0.6 * math.sin(t), 0.15 * math.sin(t * 0.7)]).as_matrix()
    return (palm @ rot.T).tolist()

def main():
    parser = argparse.ArgumentParser(description="Send deterministic mock hand keypoints")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[Mock] sending 21-point hand -> {args.host}:{args.port} at {args.fps:g} Hz")
    
    start_time = time.time()
    shoulder_pos = [0.0, 0.0, 0.0]

    try:
        while True:
            t = time.time() - start_time
            
            # 1. 手腕位置 (在舒适区画圈)
            w_x = 0.35 + 0.05 * math.cos(t) 
            w_y = 0.1 * math.sin(t)       
            w_z = 0.3                     
            wrist_pos = [w_x, w_y, w_z]

            # 2. 手腕姿态
            rot_mat = get_rotation_matrix(t)

            packet = {
                "valid": True,
                "timestamp": time.time(),
                "shoulder": shoulder_pos,
                "wrist": wrist_pos,
                "rotation": rot_mat,
                "fingers_rel": get_finger_trajectory(t),
                "hand_keypoints_21": make_hand_keypoints(t),
            }
            
            sock.sendto(json.dumps(packet).encode(), (args.host, args.port))
            print(f"\rTime: {t:.1f}s | packets: {int(t * args.fps)}", end="", flush=True)
            time.sleep(1 / max(args.fps, 1.0))

    except KeyboardInterrupt:
        print("\n停止发送。")

if __name__ == "__main__":
    main()
