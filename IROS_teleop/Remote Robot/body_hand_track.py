import pyrealsense2 as rs
import numpy as np
import cv2
import mediapipe as mp
import json
import time
import os

# ==========================================
# 工具函数：Numpy 转 List (JSON 不支持 Numpy)
# ==========================================
def to_list(obj):
    if obj is None:
        return None
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

# ==========================================
# 工具函数：获取3D点
# ==========================================
def get_3d_point(landmark, depth_frame, intrinsics, width, height):
    pixel_x = int(landmark.x * width)
    pixel_y = int(landmark.y * height)
    if pixel_x < 0 or pixel_x >= width or pixel_y < 0 or pixel_y >= height:
        return None, None
    dist = depth_frame.get_distance(pixel_x, pixel_y)
    if dist <= 0:
        return None, None
    point_3d = rs.rs2_deproject_pixel_to_point(intrinsics, [pixel_x, pixel_y], dist)
    return point_3d, (pixel_x, pixel_y)

# ==========================================
# 工具函数：计算向量
# ==========================================
def calculate_vector(p1, p2):
    if p1 is None or p2 is None: return None
    v = np.array(p2) - np.array(p1)
    norm = np.linalg.norm(v)
    if norm == 0: return None
    return v / norm

# ==========================================
# 核心算法：计算手腕旋转矩阵
# ==========================================
def calculate_wrist_orientation(wrist_3d, index_mcp_3d, pinky_mcp_3d):
    if not wrist_3d or not index_mcp_3d or not pinky_mcp_3d:
        return None
    w = np.array(wrist_3d)
    i = np.array(index_mcp_3d)
    p = np.array(pinky_mcp_3d)
    v1 = i - w
    v2 = p - w
    z_axis = np.cross(v1, v2)
    z_norm = np.linalg.norm(z_axis)
    if z_norm == 0: return None
    z_axis = z_axis / z_norm
    x_norm = np.linalg.norm(v1)
    if x_norm == 0: return None
    x_axis = v1 / x_norm
    y_axis = np.cross(z_axis, x_axis)
    return np.column_stack((x_axis, y_axis, z_axis))

# ==========================================
# 绘图函数
# ==========================================
def draw_wrist_axes(image, origin_3d, rot_matrix, intrinsics):
    if origin_3d is None or rot_matrix is None: return
    axis_length = 0.05
    origin_np = np.array(origin_3d)
    pt_x = origin_np + rot_matrix[:, 0] * axis_length
    pt_y = origin_np + rot_matrix[:, 1] * axis_length
    pt_z = origin_np + rot_matrix[:, 2] * axis_length
    try:
        px_origin = rs.rs2_project_point_to_pixel(intrinsics, origin_np)
        px_x = rs.rs2_project_point_to_pixel(intrinsics, pt_x)
        px_y = rs.rs2_project_point_to_pixel(intrinsics, pt_y)
        px_z = rs.rs2_project_point_to_pixel(intrinsics, pt_z)
        o = (int(px_origin[0]), int(px_origin[1]))
        cv2.line(image, o, (int(px_x[0]), int(px_x[1])), (0, 0, 255), 3)
        cv2.line(image, o, (int(px_y[0]), int(px_y[1])), (0, 255, 0), 3)
        cv2.line(image, o, (int(px_z[0]), int(px_z[1])), (255, 0, 0), 3)
    except: pass

def draw_origin_axes(image):
    cx, cy = 50, 50
    ln = 40
    cv2.arrowedLine(image, (cx, cy), (cx+ln, cy), (0,0,255), 2)
    cv2.putText(image, "X", (cx+ln+5, cy+5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 1)
    cv2.arrowedLine(image, (cx, cy), (cx, cy+ln), (0,255,0), 2)
    cv2.putText(image, "Y", (cx-10, cy+ln+15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
    cv2.circle(image, (cx, cy), 5, (255,0,0), -1)
    cv2.putText(image, "Z", (cx+10, cy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 1)

# ==========================================
# 主程序
# ==========================================
def main():
    mp_holistic = mp.solutions.holistic
    mp_drawing = mp.solutions.drawing_utils
    
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, 848, 480, rs.format.bgr8, 30)
    
    print("相机启动中...")
    profile = pipeline.start(config)
    align = rs.align(rs.stream.color)
    
    # 用于存储所有帧的数据列表
    recorded_data = []

    try:
        with mp_holistic.Holistic(min_detection_confidence=0.5, model_complexity=1) as holistic:
            while True:
                frames = pipeline.wait_for_frames()
                aligned_frames = align.process(frames)
                depth_frame = aligned_frames.get_depth_frame()
                color_frame = aligned_frames.get_color_frame()
                if not depth_frame or not color_frame: continue

                intrinsics = color_frame.profile.as_video_stream_profile().get_intrinsics()
                color_image = np.asanyarray(color_frame.get_data())
                h, w, _ = color_image.shape
                image_rgb = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                results = holistic.process(image_rgb)
                
                # 初始化变量
                shoulder_3d = None
                elbow_3d = None
                wrist_3d = None
                rot_matrix = None
                index_vec = None
                
                # 1. 身体检测
                if results.pose_landmarks:
                    mp_drawing.draw_landmarks(color_image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS)
                    lm = results.pose_landmarks.landmark
                    shoulder_3d, _ = get_3d_point(lm[12], depth_frame, intrinsics, w, h)
                    elbow_3d, _ = get_3d_point(lm[14], depth_frame, intrinsics, w, h)

                # 2. 手部检测
                if results.right_hand_landmarks:
                    mp_drawing.draw_landmarks(color_image, results.right_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
                    hand_lm = results.right_hand_landmarks.landmark
                    wrist_3d, _ = get_3d_point(hand_lm[0], depth_frame, intrinsics, w, h)
                    idx_root, _ = get_3d_point(hand_lm[5], depth_frame, intrinsics, w, h)
                    idx_tip, _  = get_3d_point(hand_lm[8], depth_frame, intrinsics, w, h)
                    pinky_root, _ = get_3d_point(hand_lm[17], depth_frame, intrinsics, w, h)
                    
                    rot_matrix = calculate_wrist_orientation(wrist_3d, idx_root, pinky_root)
                    index_vec = calculate_vector(idx_root, idx_tip)
                    draw_wrist_axes(color_image, wrist_3d, rot_matrix, intrinsics)
                
                draw_origin_axes(color_image)

                # ==========================================
                # 3. 构建 JSON 数据包
                # ==========================================
                current_frame_data = {
                    "timestamp": time.time(),
                    "body": {
                        "shoulder": to_list(shoulder_3d),
                        "elbow": to_list(elbow_3d)
                    },
                    "hand": {
                        "wrist_pos": to_list(wrist_3d),
                        "wrist_ori": to_list(rot_matrix),
                        "index_vec": to_list(index_vec)
                    }
                }

                # A. 实时打印 (Compact JSON string)
                json_str = json.dumps(current_frame_data)
                print(json_str)

                # B. 添加到记录列表
                recorded_data.append(current_frame_data)
                
                # 显示图像
                cv2.imshow('Teleop Data Recorder', color_image)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    finally:
        pipeline.stop()
        
        # ==========================================
        # 4. 程序结束时保存文件
        # ==========================================
        output_file = "teleop_record.json"
        print(f"\n[INFO] 正在将 {len(recorded_data)} 帧数据保存到 {output_file} ...")
        with open(output_file, 'w') as f:
            json.dump(recorded_data, f, indent=2) # indent=2 让文件有缩进，方便人阅读
        print("[INFO] 保存成功！")

if __name__ == "__main__":
    main()