"""
 * @file lbot_robot.py
 * @brief LBot机器人控制Python高级接口类
 * @author 孟凡吉
 * @date 2025.12.11
 * @copyright 灵心巧手科技有限公司
 * 
 * @details 提供高级Python接口封装，简化机器人控制操作，包含状态管理、
 *          运动控制、坐标系管理、手控制等功能。
 *          该类封装了底层API，提供更友好的Python使用体验。
"""
from .lbot_api import *
from typing import List, Tuple, Optional, Dict, Any, Callable
import threading
import time
import json


class LbotRobot:
    """
    @brief LBot机器人高级控制类
    @details 提供完整的机器人控制功能，包括连接管理、状态监控、运动控制、
             坐标系管理、L6/L10手控制等。使用Pythonic接口设计，支持上下文管理器。
    
    @example
    ```
    robot = LbotRobot("192.168.10.21")
    robot.connect()
    robot.move_to_joint_target(LbotArm.LEFT_ARM, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
    robot.disconnect()
    ```
    """
    
    def __init__(self, tcp_host: str = "127.0.0.1"):
        """
        @brief 构造函数，初始化机器人控制器
        @param tcp_host: TCP服务器地址，格式："192.168.10.21"
        """
        if api is None:
            raise RuntimeError("LbotAPI未正确初始化")
            
        self.tcp_host = tcp_host
        self._state = None
        self._state_lock = threading.Lock()
        self._connected = False
        self._state_callbacks = []
        self._error_callbacks = []
        
    def connect(self, timeout: float = 10.0) -> bool:
        """
        @brief 连接到机器人控制器
        @param timeout: 连接超时时间（秒）
        @return: True 连接成功，False 连接失败
        @note 连接成功后会自动启动状态监控
        """
        if self._connected:
            return True
            
        print(f"连接机器人: TCP {self.tcp_host}")
        success = api.init(self.tcp_host)
        
        if success:
            self._connected = True
            # 启动状态监控
            api.start_state_monitor(self._state_update_callback, self._error_callback)
            print("机器人连接成功")
            
            # 等待初始状态
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.get_state() is not None:
                    print("收到初始状态数据")
                    break
                time.sleep(0.1)
            else:
                print("警告: 未在超时时间内收到状态数据")
                
        else:
            print(f"机器人连接失败: {api.get_last_error()}")
            
        return success
    
    def disconnect(self):
        """
        @brief 断开机器人连接
        @details 停止状态监控，清理资源
        """
        if self._connected:
            print("断开机器人连接...")
            api.stop_state_monitor()
            api.cleanup()
            self._connected = False
            self._state = None
            self._state_callbacks.clear()
            self._error_callbacks.clear()
            print("机器人已断开连接")
    
    def is_connected(self) -> bool:
        """
        @brief 检查是否已连接到机器人
        @return: True 已连接，False 未连接
        """
        return self._connected
    
    def get_controller_info(self) -> Optional[Dict[str, str]]:
        """
        @brief 获取控制器信息
        @return: 控制器信息字典，包含robot_model和controller_version，
                 如果获取失败则返回None
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return None
        
        success, robot_model, controller_version = api.get_controller_info()
        if success:
            return {
                'robot_model': robot_model or "Unknown",
                'controller_version': controller_version or "Unknown"
            }
        else:
            print(f"获取控制器信息失败: {api.get_last_error()}")
            return None
    
    def _state_update_callback(self, state: LbotFullState):
        """
        @brief 内部状态更新回调函数
        @param state: 机器人完整状态数据
        @internal 此函数由底层API调用，用户不应直接调用
        """
        with self._state_lock:
            self._state = state
        
        # 调用外部注册的回调
        for callback in self._state_callbacks:
            try:
                callback(state)
            except Exception as e:
                print(f"状态回调执行错误: {e}")
    
    def _error_callback(self, error_code: int, error_msg: str):
        """
        @brief 内部错误回调函数
        @param error_code: 错误代码
        @param error_msg: 错误消息
        @internal 此函数由底层API调用，用户不应直接调用
        """
        print(f"机器人错误: 代码={error_code}, 消息={error_msg}")
        
        # 调用外部注册的错误回调
        for callback in self._error_callbacks:
            try:
                callback(error_code, error_msg)
            except Exception as e:
                print(f"错误回调执行错误: {e}")
    
    def add_state_callback(self, callback: Callable[[LbotFullState], None]):
        """
        @brief 添加状态更新回调函数
        @param callback: 回调函数，接收一个LbotFullState参数
        """
        if callback not in self._state_callbacks:
            self._state_callbacks.append(callback)
    
    def remove_state_callback(self, callback: Callable[[LbotFullState], None]):
        """
        @brief 移除状态更新回调函数
        @param callback: 要移除的回调函数
        """
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)
    
    def add_error_callback(self, callback: Callable[[int, str], None]):
        """
        @brief 添加错误回调函数
        @param callback: 回调函数，接收错误代码和错误消息两个参数
        """
        if callback not in self._error_callbacks:
            self._error_callbacks.append(callback)
    
    def remove_error_callback(self, callback: Callable[[int, str], None]):
        """
        @brief 移除错误回调函数
        @param callback: 要移除的回调函数
        """
        if callback in self._error_callbacks:
            self._error_callbacks.remove(callback)
    
    def get_state(self) -> Optional[LbotFullState]:
        """
        @brief 获取当前机器人完整状态
        @return: 机器人状态对象，如果未连接则返回None
        @note 需要在启动状态监控后才能获取有效状态
        """
        with self._state_lock:
            return self._state
    
    def get_state_dict(self) -> Optional[Dict[str, Any]]:
        """
        @brief 获取当前机器人状态（字典格式）
        @return: 状态字典，包含所有状态信息
        """
        state = self.get_state()
        if state:
            return state.to_dict()
        return None
    
    def get_joint_positions(self, arm: LbotArm) -> Optional[List[float]]:
        """
        @brief 获取关节位置
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @return: 7个关节角度值列表（弧度），如果获取失败则返回None
        """
        state = self.get_state()
        if state:
            if arm == LbotArm.LEFT_ARM:
                return state.left_arm.get_joints_list()
            else:
                return state.right_arm.get_joints_list()
        return None
    
    def get_cartesian_pose(self, arm: LbotArm) -> Optional[Tuple[LbotPosition, LbotEuler]]:
        """
        @brief 获取笛卡尔空间位姿
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @return: 元组(位置, 欧拉角)，如果获取失败则返回None
        """
        state = self.get_state()
        if state:
            if arm == LbotArm.LEFT_ARM:
                return state.left_arm.end_effector_position, state.left_arm.euler
            else:
                return state.right_arm.end_effector_position, state.right_arm.euler
        return None
    
    def get_cartesian_pose_dict(self, arm: LbotArm) -> Optional[Dict[str, Any]]:
        """
        @brief 获取笛卡尔空间位姿（字典格式）
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @return: 位姿字典，包含位置和欧拉角信息
        """
        pose = self.get_cartesian_pose(arm)
        if pose:
            position, euler = pose
            return {
                'position': position.to_dict(),
                'euler': euler.to_dict()
            }
        return None
    
    def move_to_joint_target(self, arm: LbotArm, target_joints: List[float], 
                           speed: float = 0.5, accel: float = 0.1, 
                           block: bool = True) -> bool:
        """
        @brief 关节空间运动控制
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param target_joints: 7个关节的目标角度（弧度）
        @param speed: 运动速度（0.0~20.0）单位是rad/s
        @param accel: 加速度（0.0~20.0）单位是rad/s²
        @param block: 是否阻塞执行：True 等待运动完成，False 立即返回
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.move_joint(arm, target_joints, speed, accel, block)
    
    def move_to_pose_target(self, arm: LbotArm, position: LbotPosition, 
                          euler: LbotEuler, speed: float = 0.5, 
                          accel: float = 0.1, block: bool = True) -> bool:
        """
        @brief 笛卡尔空间姿态运动（关节插值）
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param position: 目标位置（x, y, z，单位：米）
        @param euler: 机械臂末端目标欧拉角（roll, pitch, yaw，单位：弧度）
        @param speed: 机械臂末端运动速度（0.0~20.0）单位m/s
        @param accel: 机械臂末端加速度（0.0~1.0）单位m/s²
        @param block: 是否阻塞执行：True 等待运动完成，False 立即返回
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.move_pose(arm, position, euler, speed, accel, block)
    
    def linear_move_to_pose(self, arm: LbotArm, position: LbotPosition, 
                          euler: LbotEuler, speed: float = 0.5, 
                          accel: float = 0.1, block: bool = True) -> bool:
        """
        @brief 笛卡尔空间直线运动（直线插值）
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param position: 目标位置（x, y, z，单位：米）
        @param euler: 目标欧拉角（roll, pitch, yaw，单位：弧度）
        @param speed: 关节运动速度（0.0~20.0）单位是rad/s
        @param accel: 关节运动加速度（0.0~20.0）单位是rad/s²
        @param block: 是否阻塞执行：True 等待运动完成，False 立即返回
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.move_linear(arm, position, euler, speed, accel, block)
    
    def joint_follow(self, arm: LbotArm, joints: List[float], follow: bool = True) -> bool:
        """
        @brief 关节跟随控制（用于遥操作）
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param joints: 7个关节的目标角度（弧度）
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.joint_follow(arm, joints, follow)
    
    # ==============================================
    # L6手控制接口
    # ==============================================
    
    def l6_set_position(self, arm: LbotArm, position: List[int]) -> bool:
        """
        @brief 设置L6手的位置控制
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param position: 6个手指的目标位置列表 (0~255)
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.l6_set_position(arm, position)
    
    def l6_set_velocity(self, arm: LbotArm, velocity: List[int]) -> bool:
        """
        @brief 设置L6手的速度控制
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param velocity: 6个手指的目标速度列表 (0~255)
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.l6_set_velocity(arm, velocity)
    
    def l6_set_effort(self, arm: LbotArm, effort: List[int]) -> bool:
        """
        @brief 设置L6手的力矩控制
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param effort: 6个手指的目标力矩列表 (0~255)
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.l6_set_effort(arm, effort)
    
    # ==============================================
    # L10手控制接口 - 新增
    # ==============================================
    
    def l10_set_position(self, arm: LbotArm, position: List[int]) -> bool:
        """
        @brief 设置L10手的位置控制
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param position: 10个手指的目标位置列表 (0~255)
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.l10_set_position(arm, position)
    
    def l10_set_velocity(self, arm: LbotArm, velocity: List[int]) -> bool:
        """
        @brief 设置L10手的速度控制
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param velocity: 10个手指的目标速度列表 (0~255)
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.l10_set_velocity(arm, velocity)
    
    def l10_set_effort(self, arm: LbotArm, effort: List[int]) -> bool:
        """
        @brief 设置L10手的力矩控制
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param effort: 10个手指的目标力矩列表 (0~255)
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.l10_set_effort(arm, effort)
    
    def compute_forward_kinematics(self, arm: LbotArm, joints: List[float]) -> Optional[Tuple[LbotPosition, LbotEuler]]:
        """
        @brief 正运动学计算
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param joints: 7个关节角度（弧度）
        @return: 元组(末端位置, 末端欧拉角)，如果计算失败则返回None
        """
        success, position, euler = api.forward_kinematics(arm, joints)
        if success:
            return position, euler
        return None
    
    def compute_inverse_kinematics(self, arm: LbotArm, position: LbotPosition, 
                                 euler: LbotEuler, initial_joints: List[float] = None) -> Optional[List[float]]:
        """
        @brief 逆运动学计算
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param position: 目标位置（x, y, z，单位：米）
        @param euler: 目标欧拉角（roll, pitch, yaw，单位：弧度）
        @param initial_joints: 初始关节角度（弧度），用于求解器迭代，如果为None则使用当前位置
        @return: 7个关节角度解（弧度），如果求解失败则返回None
        """
        if initial_joints is None:
            # 使用当前关节位置作为初始值
            current_joints = self.get_joint_positions(arm)
            if current_joints:
                initial_joints = current_joints
            else:
                initial_joints = [0.0] * 7
        
        success, result_joints = api.inverse_kinematics(arm, initial_joints, position, euler)
        if success:
            return result_joints
        return None
    
    def set_tool_frame(self, arm: LbotArm, name: str, position: LbotPosition, 
                      euler: LbotEuler) -> bool:
        """
        @brief 设置工具坐标系
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param name: 工具坐标系名称（最大32字符）
        @param position: 工具坐标系相对于法兰盘的位置偏移（x, y, z，单位：米）
        @param euler: 工具坐标系相对于法兰盘的欧拉角偏移（roll, pitch, yaw，单位：弧度）
        @return: True 设置成功，False 设置失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.set_tool_frame(arm, name, position, euler)
    
    def get_tool_frame(self, arm: LbotArm, name: str) -> Optional[Tuple[LbotPosition, LbotEuler]]:
        """
        @brief 获取工具坐标系参数
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param name: 工具坐标系名称
        @return: 元组(位置偏移, 欧拉角偏移)，如果获取失败则返回None
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return None
        success, position, euler = api.get_tool_frame(arm, name)
        if success:
            return position, euler
        return None
    
    def get_current_tool_frame(self, arm: LbotArm) -> Optional[Tuple[str, LbotPosition, LbotEuler]]:
        """
        @brief 获取当前使用的工具坐标系
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @return: 元组(名称, 位置偏移, 欧拉角偏移)，如果获取失败则返回None
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return None
        success, name, position, euler = api.get_current_tool_frame(arm)
        if success:
            return name, position, euler
        return None
    
    def change_tool_frame(self, arm: LbotArm, name: str) -> bool:
        """
        @brief 切换当前工具坐标系
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param name: 要切换到的工具坐标系名称
        @return: True 切换成功，False 切换失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.change_tool_frame(arm, name)
    
    def delete_tool_frame(self, arm: LbotArm, name: str) -> bool:
        """
        @brief 删除工具坐标系
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param name: 要删除的工具坐标系名称
        @return: True 删除成功，False 删除失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.delete_tool_frame(arm, name)
    
    def get_all_tool_frames(self, arm: LbotArm) -> Optional[List[str]]:
        """
        @brief 获取所有工具坐标系名称
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @return: 工具坐标系名称列表，如果获取失败则返回None
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return None
        success, names = api.get_all_tool_frames(arm)
        if success:
            return names
        return None
    
    def set_work_frame(self, arm: LbotArm, name: str, position: LbotPosition, 
                      euler: LbotEuler) -> bool:
        """
        @brief 设置工作坐标系
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param name: 工作坐标系名称（最大32字符）
        @param position: 工作坐标系相对于基坐标系的位置偏移（x, y, z，单位：米）
        @param euler: 工作坐标系相对于基坐标系的欧拉角偏移（roll, pitch, yaw，单位：弧度）
        @return: True 设置成功，False 设置失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.set_work_frame(arm, name, position, euler)
    
    def get_work_frame(self, arm: LbotArm, name: str) -> Optional[Tuple[LbotPosition, LbotEuler]]:
        """
        @brief 获取工作坐标系参数
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param name: 工作坐标系名称
        @return: 元组(位置偏移, 欧拉角偏移)，如果获取失败则返回None
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return None
        success, position, euler = api.get_work_frame(arm, name)
        if success:
            return position, euler
        return None
    
    def change_work_frame(self, arm: LbotArm, name: str) -> bool:
        """
        @brief 切换当前工作坐标系
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param name: 要切换到的工作坐标系名称
        @return: True 切换成功，False 切换失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.change_work_frame(arm, name)
    
    def delete_work_frame(self, arm: LbotArm, name: str) -> bool:
        """
        @brief 删除工作坐标系
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param name: 要删除的工作坐标系名称
        @return: True 删除成功，False 删除失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.delete_work_frame(arm, name)
    
    def get_all_work_frames(self, arm: LbotArm) -> Optional[List[str]]:
        """
        @brief 获取所有工作坐标系名称
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @return: 工作坐标系名称列表，如果获取失败则返回None
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return None
        success, names = api.get_all_work_frames(arm)
        if success:
            return names
        return None
    
    def create_tool_frame_by_teaching(self, arm: LbotArm, name: str) -> bool:
        """
        @brief 通过示教创建工具坐标系
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param name: 工具坐标系名称
        @return: True 创建成功，False 创建失败
        @note 需要用户交互操作
        """
        print(f"正在示教工具坐标系 {name}...")
        print("1. 请将工具尖端对准一个参考点")
        input("按回车键记录第一个点...")
        
        pose1 = self.get_cartesian_pose(arm)
        if not pose1:
            print("错误: 无法获取当前位姿")
            return False
        
        print("2. 请将工具尖端旋转一定角度对准同一个参考点")
        input("按回车键记录第二个点...")
        
        pose2 = self.get_cartesian_pose(arm)
        if not pose2:
            print("错误: 无法获取当前位姿")
            return False
        
        # 这里应该实现具体的工具坐标系计算逻辑
        # 简化版本：使用第一个点的位置，欧拉角保持当前值
        position, euler = pose1
        return self.set_tool_frame(arm, name, position, euler)
    
    def create_work_frame_by_three_points(self, arm: LbotArm, name: str) -> bool:
        """
        @brief 通过三点法创建工作坐标系
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param name: 工作坐标系名称
        @return: True 创建成功，False 创建失败
        @note 需要用户交互操作
        """
        print(f"正在创建三点法工作坐标系 {name}...")
        print("1. 原点点")
        input("将工具移动到原点位置，按回车记录...")
        origin = self.get_cartesian_pose(arm)
        if not origin:
            return False
        
        print("2. X轴方向点")
        input("将工具移动到X轴正方向位置，按回车记录...")
        x_point = self.get_cartesian_pose(arm)
        if not x_point:
            return False
        
        print("3. Y轴方向点")
        input("将工具移动到XY平面内任意一点，按回车记录...")
        y_point = self.get_cartesian_pose(arm)
        if not y_point:
            return False
        
        # 这里应该实现三点法计算坐标系的逻辑
        # 简化版本：使用原点的位置，保持当前欧拉角
        position, euler = origin
        return self.set_work_frame(arm, name, position, euler)
    
    def print_coordinate_frames(self, arm: LbotArm):
        """
        @brief 打印所有坐标系信息
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        """
        print(f"\n=== {arm.name} 机械臂坐标系信息 ===")
        
        # 当前工具坐标系
        current_tool = self.get_current_tool_frame(arm)
        if current_tool:
            name, position, euler = current_tool
            print(f"当前工具坐标系: {name}")
            print(f"  位置: {position}")
            print(f"  欧拉角: {euler}")
        
        # 所有工具坐标系
        print("\n所有工具坐标系:")
        tool_frames = self.get_all_tool_frames(arm)
        if tool_frames:
            for name in tool_frames:
                if current_tool and name == current_tool[0]:
                    continue
                frame = self.get_tool_frame(arm, name)
                if frame:
                    position, euler = frame
                    print(f"  {name}: 位置={position}, 欧拉角={euler}")
        else:
            print("  无其他工具坐标系")
        
        # 工作坐标系
        print("\n工作坐标系:")
        work_frames = self.get_all_work_frames(arm)
        if work_frames:
            for name in work_frames:
                frame = self.get_work_frame(arm, name)
                if frame:
                    position, euler = frame
                    print(f"  {name}: 位置={position}, 欧拉角={euler}")
        else:
            print("  无工作坐标系")
        
        print("=" * 40)
    
    def print_system_info(self):
        """
        @brief 打印系统信息
        @details 包括控制器信息、连接状态、关节位置、笛卡尔位姿等
        """
        print("=== 系统信息 ===")
        # 控制器信息
        controller_info = self.get_controller_info()
        if controller_info:
            print(f"机器人型号: {controller_info['robot_model']}")
            print(f"控制器版本: {controller_info['controller_version']}")
        else:
            print("控制器信息: 不可用")
        
        # 连接状态
        print(f"连接状态: {'已连接' if self._connected else '未连接'}")
        
        # 当前状态
        state = self.get_state()
        if state:
            print(f"状态时间戳: {state.timestamp}")
            left_joints = state.left_arm.get_joints_list()
            right_joints = state.right_arm.get_joints_list()
            print(f"左臂关节: {[f'{j:.3f}' for j in left_joints]}")
            print(f"右臂关节: {[f'{j:.3f}' for j in right_joints]}")
            
            # 添加笛卡尔位姿信息
            left_pose = self.get_cartesian_pose(LbotArm.LEFT_ARM)
            right_pose = self.get_cartesian_pose(LbotArm.RIGHT_ARM)
            if left_pose:
                pos, euler = left_pose
                print(f"左臂位姿: 位置={pos}, 欧拉角={euler}")
            if right_pose:
                pos, euler = right_pose
                print(f"右臂位姿: 位置={pos}, 欧拉角={euler}")
        else:
            print("当前状态: 不可用")
        
        print("================")

    def set_zero(self, arm: LbotArm) -> bool:
        """
        @brief 重新标定电机零位，设置当前位置为零位
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @return: True 设置成功，False 设置失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.set_zero(arm)
    
    def enable_arm(self, arm: LbotArm, enable: bool = True) -> bool:
        """
        @brief 使能/掉使能机械臂
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param enable: True 使能，False 掉使能
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.enable_arm(arm, enable)
    
    def emergency_stop(self, arm: LbotArm, enable: bool = True) -> bool:
        """
        @brief 紧急停止/恢复
        @param arm: 机械臂选择：LbotArm.LEFT_ARM 或 LbotArm.RIGHT_ARM
        @param enable: True 紧急停止，False 恢复运行
        @return: True 指令发送成功，False 发送失败
        """
        if not self._connected:
            print("错误: 机器人未连接")
            return False
        return api.emergency_stop(arm, enable)
    
    def clear_errors(self) -> bool:
        """
        @brief 清除所有错误
        @return: True 清除成功，False 清除失败
        """
        return api.clear_errors()
    
    def get_last_error(self) -> str:
        """
        @brief 获取最后一次错误信息
        @return: 错误信息字符串
        """
        return api.get_last_error()
    
    def wait_for_motion_completion(self, timeout: float = 30.0) -> bool:
        """
        @brief 等待运动完成
        @param timeout: 等待超时时间（秒）
        @return: True 运动完成，False 超时
        @note 这是一个简化实现，实际应该检查运动状态
        """
        print("等待运动完成...")
        time.sleep(2)  # 简化实现，实际应该检查运动状态
        return True
    
    def save_state_to_file(self, filename: str):
        """
        @brief 保存当前状态到JSON文件
        @param filename: 文件名
        """
        state_dict = self.get_state_dict()
        if state_dict:
            with open(filename, 'w') as f:
                json.dump(state_dict, f, indent=2)
            print(f"状态已保存到: {filename}")
        else:
            print("无法获取状态数据")
    
    def __enter__(self):
        """
        @brief 上下文管理器入口
        @return: 当前对象
        """
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        @brief 上下文管理器出口
        @param exc_type: 异常类型
        @param exc_val: 异常值
        @param exc_tb: 异常跟踪信息
        """
        self.disconnect()


# 导出
__all__ = ['LbotRobot']