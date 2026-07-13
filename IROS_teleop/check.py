import pinocchio as pin
import os
import sys

# ================= 配置 =================
# 你的 URDF 路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
URDF_PATH = os.path.join(CURRENT_DIR, "config/combined_robot/robot.urdf")
PACKAGE_DIRS = [os.path.join(CURRENT_DIR, "config/combined_robot")]

def main():
    if not os.path.exists(URDF_PATH):
        print(f"❌ 找不到文件: {URDF_PATH}")
        return

    print(f"📂 正在加载: {URDF_PATH} ...\n")
    
    try:
        # 加载模型
        robot = pin.RobotWrapper.BuildFromURDF(URDF_PATH, package_dirs=PACKAGE_DIRS, root_joint=None)
        model = robot.model
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return

    print("="*60)
    print(f"🤖 机器人包含 {model.njoints} 个关节 (Joints) 和 {model.nframes} 个坐标系 (Frames)")
    print("="*60)

    # --- 1. 打印所有可控关节 (Joints) ---
    print("\n🔧 [可控关节名称] (用于初始化 self.q 或控制电机):")
    print("-" * 30)
    # 跳过 universe (id=0)
    for i in range(1, model.njoints):
        name = model.names[i]
        print(f"  ID {i}: '{name}'")

    # --- 2. 打印所有末端连杆 (Frames/Links) ---
    print("\n📍 [连杆/坐标系名称] (用于 WRIST_FRAME 和 FINGER_FRAMES):")
    print("-" * 30)
    print("👉 请在下面寻找你的 指尖(tip/distal) 和 手腕(wrist) 的准确名字：")
    
    # 过滤掉一些无关的 frame，只显示 Body 类型的
    for frame in model.frames:
        # 只打印 Link (BODY) 或者 Fixed Joint 产生的 Frame
        if frame.type == pin.FrameType.BODY:
            name = frame.name
            # 简单高亮一下可能是指尖的名字
            if "tip" in name or "distal" in name or "finger" in name:
                print(f"  ✨ '{name}'  <-- 可能是指尖?")
            elif "wrist" in name or "hand" in name:
                print(f"  🖐  '{name}'  <-- 可能是手腕?")
            else:
                print(f"  '{name}'")

    print("\n" + "="*60)
    print("✅ 检查完毕！")
    print("1. 请把带 ✨ 的名字填入 kinematics_server.py 的 ROBOT_FINGERS 列表。")
    print("2. 请把带 🖐 的名字填入 ROBOT_WRIST_FRAME。")
    print("3. 如果名字不一样，程序会报错找不到 Link。")

if __name__ == "__main__":
    main()