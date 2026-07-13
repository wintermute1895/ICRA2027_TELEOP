import socket
import json
import time
import math
import numpy as np
from scipy.spatial.transform import Rotation as R

# === 配置 ===
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
FPS = 30

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

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"📡 [Mock Client - Better Hand] 启动 -> {UDP_IP}:{UDP_PORT}")
    print("   - 优化了手指轨迹：扇形张开 -> 掌心聚拢")
    
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

            # 3. 手指数据 (新的函数)
            fingers_data = get_finger_trajectory(t)

            packet = {
                "valid": True,
                "timestamp": time.time(),
                "shoulder": shoulder_pos,
                "wrist": wrist_pos,
                "rotation": rot_mat,
                "fingers_rel": fingers_data
            }
            
            sock.sendto(json.dumps(packet).encode(), (UDP_IP, UDP_PORT))
            print(f"\rTime: {t:.1f}s | Grip: {'✊' if (math.sin(t*3)+1)/2 > 0.5 else '🖐️'}", end="")
            time.sleep(1/FPS)

    except KeyboardInterrupt:
        print("\n停止发送。")

if __name__ == "__main__":
    main()