import pyrealsense2 as rs
import numpy as np
import cv2
import mediapipe as mp
import json
import socket
import time

# === 配置 ===
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
LINK_SCALE = 1.2 # 臂长缩放

def map_vector(v_cam):
    """ 摄像头坐标 -> 机器人坐标 (和之前一样) """
    x, y, z = v_cam
    return np.array([-z, -x, -y])

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(min_detection_confidence=0.7)
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
    mp_draw = mp.solutions.drawing_utils

    # RealSense
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    profile = pipeline.start(config)
    intrinsics = profile.get_stream(rs.stream.color).as_video_stream_profile().intrinsics

    print(f"👀 [Vision Pro] 全身捕捉启动 -> {UDP_IP}:{UDP_PORT}")
    print("   - 手臂: 双向量控制")
    print("   - 手指: 21点全骨架传输 (for Dex-Retargeting)")

    try:
        while True:
            frames = pipeline.wait_for_frames()
            depth_frame = frames.get_depth_frame()
            color_frame = frames.get_color_frame()
            if not depth_frame or not color_frame: continue

            img = np.asanyarray(color_frame.get_data())
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            res_pose = pose.process(rgb)
            res_hands = hands.process(rgb)
            
            packet = {
                "timestamp": time.time(), "valid": False,
                "rotation": np.eye(3).tolist()
            }

            # 1. 手臂双向量
            if res_pose.pose_landmarks:
                lm = res_pose.pose_landmarks.landmark
                h, w, _ = img.shape
                id_sh, id_el, id_wr = 12, 14, 16 # 右侧 肩-肘-腕
                
                # 提取坐标
                pts = []
                for idx in [id_sh, id_el, id_wr]:
                    px, py = int(lm[idx].x * w), int(lm[idx].y * h)
                    if 0 <= px < w and 0 <= py < h:
                        d = depth_frame.get_distance(px, py)
                        if 0.2 < d < 2.0:
                            pts.append(rs.rs2_deproject_pixel_to_point(intrinsics, [px, py], d))
                
                if len(pts) == 3:
                    p_sh, p_el, p_wr = [np.array(p) for p in pts]
                    
                    # 计算并映射向量
                    v_upper = map_vector(p_el - p_sh) * LINK_SCALE
                    v_fore  = map_vector(p_wr - p_el) * LINK_SCALE
                    
                    packet["valid"] = True
                    packet["vec_upper"] = v_upper.tolist()
                    packet["vec_fore"] = v_fore.tolist()

            # 2. 手指 21 点骨架 (关键升级)
            if res_hands.multi_hand_landmarks and packet["valid"]:
                hand_lm = res_hands.multi_hand_landmarks[0]
                mp_draw.draw_landmarks(img, hand_lm, mp_hands.HAND_CONNECTIONS)
                
                # 提取 21 个关键点 (相对于手腕)
                # MediaPipe 顺序: 0(腕), 1-4(拇), 5-8(食), 9-12(中), 13-16(无), 17-20(小)
                keypoints_rel = []
                wrist_node = hand_lm.landmark[0]
                
                # 我们需要保留原始的相对结构，不要乱缩放，Dex-Retargeting 算法会处理
                # 这里我们转换到 Camera 坐标系的尺度 (MediaPipe 的 Z 是相对的，这里简单处理)
                # 为了精度，我们直接发送归一化的 (x,y,z) 差值，或者全部用像素深度反投影
                # 简单起见：发送归一化的相对坐标，Server 端做尺度对齐
                
                for i in range(21):
                    lm = hand_lm.landmark[i]
                    # 发送相对坐标 (x, -y, -z) 简单的方向调整
                    # 注意：MP的坐标系和机器人手掌通常不同，这里发原始数据，Server端去配对
                    kp = [lm.x - wrist_node.x, lm.y - wrist_node.y, lm.z - wrist_node.z]
                    keypoints_rel.append(kp)
                
                packet["hand_keypoints_21"] = keypoints_rel

            if packet["valid"]:
                sock.sendto(json.dumps(packet).encode(), (UDP_IP, UDP_PORT))

            cv2.imshow('Teleop Vision', cv2.flip(img, 1))
            if cv2.waitKey(1) == ord('q'): break

    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()