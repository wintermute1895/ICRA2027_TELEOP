"""
 * @file lbot_api.py
 * @brief Python绑定库，对应lbot_types.h中定义的结构和枚举
 * @author 孟凡吉
 * @date 2025.12.11
 * @copyright 灵心巧手科技有限公司
 *
"""
import ctypes
import os
import sys
import platform
from ctypes import *
from typing import Callable, List, Optional, Any, Dict, Tuple
import threading
from enum import IntEnum
import inspect

class LbotConfig:
    """配置类"""
    # 库文件配置
    LIBRARY_PATHS = {
        'linux': {
            'x86_64': "libs/linux/linux_x64/liblbot_api.so",
            'aarch64': "libs/linux/linux_arm64/liblbot_api.so",
            'arm64': "libs/linux/linux_arm64/liblbot_api.so"
        },
        'windows': {
            'x86_64': "libs/windows/lbot_api.dll",
            'amd64': "libs/windows/lbot_api.dll"
        },
        'darwin': {
            'x86_64': "libs/macos/liblbot_api.dylib",
            'arm64': "libs/macos/liblbot_api.dylib"
        }
    }
    
    # 备选库文件名
    ALTERNATIVE_LIB_NAMES = [
        "liblbot_api.so",
        "liblbot_api.so.1", 
        "liblbot_api.so.1.0.0",
        "liblbot_api_cpp.so",
        "lbot_api.dll",
        "liblbot_api.dylib"
    ]


# 枚举定义
class LbotArm(IntEnum):
    LEFT_ARM = 0
    RIGHT_ARM = 1

class LbotMoveType(IntEnum):
    MOVE_JOINT = 0
    MOVE_POSE = 1
    MOVE_LINEAR = 2


# 结构体定义 - 改为独立类定义
class LbotPosition(Structure):
    _fields_ = [
        ("x", c_double),
        ("y", c_double),
        ("z", c_double)
    ]
    
    def __init__(self, x=0.0, y=0.0, z=0.0):
        super().__init__()
        self.x = x
        self.y = y
        self.z = z
    
    def __repr__(self):
        return f"Position(x={self.x:.3f}, y={self.y:.3f}, z={self.z:.3f})"
    
    def to_list(self):
        return [self.x, self.y, self.z]
    
    def to_dict(self):
        return {'x': self.x, 'y': self.y, 'z': self.z}


class LbotOrientation(Structure):
    _fields_ = [
        ("x", c_double),
        ("y", c_double),
        ("z", c_double),
        ("w", c_double)
    ]
    
    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0):
        super().__init__()
        self.x = x
        self.y = y
        self.z = z
        self.w = w
    
    def __repr__(self):
        return f"Orientation(x={self.x:.3f}, y={self.y:.3f}, z={self.z:.3f}, w={self.w:.3f})"
    
    def to_dict(self):
        return {'x': self.x, 'y': self.y, 'z': self.z, 'w': self.w}


class LbotEuler(Structure):
    _fields_ = [
        ("x", c_double),
        ("y", c_double),
        ("z", c_double)
    ]
    
    def __init__(self, x=0.0, y=0.0, z=0.0):
        super().__init__()
        self.x = x
        self.y = y
        self.z = z
    
    def __repr__(self):
        return f"Euler(x={self.x:.3f}, y={self.y:.3f}, z={self.z:.3f})"
    
    def to_list(self):
        return [self.x, self.y, self.z]
    
    def to_dict(self):
        return {'x': self.x, 'y': self.y, 'z': self.z}


class LbotArmState(Structure):
    _fields_ = [
        ("name", c_char * 7 * 32),         # 7个关节名称，每个最多32字符
        ("joint_position", c_double * 7),  # 7个关节位置（与C头文件一致）
        ("velocity", c_double * 7),        # 7个关节速度
        ("effort", c_double * 7),         # 7个关节力矩
        ("sec", c_int32),                 # 秒
        ("nanosec", c_uint32),           # 纳秒
        ("frame_id", c_char * 64),       # 帧ID
        ("end_effector_position", LbotPosition),  # 末端位置
        ("euler", LbotEuler),                    # 欧拉角
        ("orientation", LbotOrientation)        # 四元数姿态
    ]
    
    def get_joints_list(self):
        return [self.joint_position[i] for i in range(7)]
    
    def get_joint_names(self):
        """获取关节名称列表"""
        names = []
        for i in range(7):
            name_bytes = self.name[i]
            # 找到第一个null终止符
            null_index = name_bytes.find(b'\x00')
            if null_index != -1:
                name_bytes = name_bytes[:null_index]
            names.append(name_bytes.decode('utf-8', errors='ignore'))
        return names
    
    def get_velocities_list(self):
        return [self.velocity[i] for i in range(7)]
    
    def get_efforts_list(self):
        return [self.effort[i] for i in range(7)]
    
    def get_timestamp(self):
        return f"{self.sec}.{self.nanosec:09d}"
    
    def get_frame_id(self):
        return self.frame_id.decode('utf-8', errors='ignore')
    
    def __repr__(self):
        joints_list = self.get_joints_list()
        return f"ArmState(joints={[f'{j:.3f}' for j in joints_list]}, position={self.end_effector_position}, euler={self.euler})"
    
    def to_dict(self):
        return {
            'joint_names': self.get_joint_names(),
            'joints': self.get_joints_list(),
            'velocities': self.get_velocities_list(),
            'efforts': self.get_efforts_list(),
            'timestamp': {
                'sec': self.sec,
                'nanosec': self.nanosec,
                'string': self.get_timestamp()
            },
            'frame_id': self.get_frame_id(),
            'position': self.end_effector_position.to_dict(),
            'euler': self.euler.to_dict(),
            'orientation': self.orientation.to_dict()
        }


class LbotFullState(Structure):
    _fields_ = [
        ("left_arm", LbotArmState),
        ("right_arm", LbotArmState),
        ("timestamp", c_uint64)
    ]
    
    def __repr__(self):
        return f"FullState(timestamp={self.timestamp})"
    
    def to_dict(self):
        return {
            'left_arm': self.left_arm.to_dict(),
            'right_arm': self.right_arm.to_dict(),
            'timestamp': self.timestamp
        }


class LibraryLoader:
    """库加载器"""
    
    @staticmethod
    def get_library_path():
        """根据系统架构获取库文件路径"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # 首先尝试配置的路径
        if system in LbotConfig.LIBRARY_PATHS:
            if machine in LbotConfig.LIBRARY_PATHS[system]:
                lib_relative_path = LbotConfig.LIBRARY_PATHS[system][machine]
                lib_path = os.path.join(current_dir, lib_relative_path)
                if os.path.exists(lib_path):
                    return lib_path
        
        # 备选方案：在libs目录下搜索
        libs_dir = os.path.join(current_dir, "libs")
        if os.path.exists(libs_dir):
            for root, dirs, files in os.walk(libs_dir):
                for lib_name in LbotConfig.ALTERNATIVE_LIB_NAMES:
                    test_path = os.path.join(root, lib_name)
                    if os.path.exists(test_path):
                        return test_path
        
        raise ImportError(f"未找到合适的库文件。系统: {system}, 架构: {machine}")

    @staticmethod
    def load_library():
        """加载C库"""
        lib_path = LibraryLoader.get_library_path()
        print(f"正在加载库: {lib_path}")
        
        try:
            lib = cdll.LoadLibrary(lib_path)
            print("库加载成功")
            return lib
        except Exception as e:
            raise ImportError(f"无法加载库文件 {lib_path}: {e}")


class FunctionPrototypeManager:
    """函数原型管理器"""
    
    # 函数原型定义 - 根据C头文件更新
    FUNCTION_PROTOTYPES = {
        # API初始化与清理
        'lbot_init': ([c_char_p], c_bool),
        'lbot_cleanup': ([], None),
        
        # 系统信息获取
        'lbot_get_controller_info': ([POINTER(c_char_p), POINTER(c_char_p)], c_bool),
        
        # 状态监控
        'lbot_start_state_monitor': ([CFUNCTYPE(None, POINTER(LbotFullState)), 
                                    CFUNCTYPE(None, c_int, c_char_p)], c_bool),
        'lbot_stop_state_monitor': ([], None),
        'lbot_get_current_state': ([POINTER(LbotFullState)], c_bool),
        
        # 基础运动控制
        'lbot_move_joint': ([c_int, POINTER(c_double), c_double, c_double, c_bool], c_bool),
        'lbot_move_pose': ([c_int, POINTER(LbotPosition), 
                          POINTER(LbotEuler), c_double, c_double, c_bool], c_bool),
        'lbot_move_linear': ([c_int, POINTER(LbotPosition), 
                            POINTER(LbotEuler), c_double, c_double, c_bool], c_bool),
        
        # 关节跟随函数 - 统一接口
        'lbot_joint_follow': ([c_int, POINTER(c_double), c_bool], c_bool),
        
        # ==============================================
        # L6手控制接口
        # ==============================================
        'lbot_l6_set_position': ([c_int, POINTER(c_uint8)], c_bool),
        'lbot_l6_set_velocity': ([c_int, POINTER(c_uint8)], c_bool),
        'lbot_l6_set_effort': ([c_int, POINTER(c_uint8)], c_bool),
        
        # ==============================================
        # L10手控制接口 - 新增
        # ==============================================
        'lbot_l10_set_position': ([c_int, POINTER(c_uint8)], c_bool),
        'lbot_l10_set_velocity': ([c_int, POINTER(c_uint8)], c_bool),
        'lbot_l10_set_effort': ([c_int, POINTER(c_uint8)], c_bool),
        
        # 运动学计算
        'lbot_forward_kinematics': ([c_int, POINTER(c_double), POINTER(LbotPosition), 
                                   POINTER(LbotEuler)], c_bool),
        'lbot_inverse_kinematics': ([c_int, POINTER(c_double), POINTER(LbotPosition), 
                                   POINTER(LbotEuler), POINTER(c_double)], c_bool),
        
        # 工具坐标系管理
        'lbot_set_tool_frame': ([c_int, c_char_p, POINTER(LbotPosition), 
                               POINTER(LbotEuler)], c_bool),
        'lbot_get_tool_frame': ([c_int, c_char_p, POINTER(LbotPosition), 
                               POINTER(LbotEuler)], c_bool),
        'lbot_get_current_tool_frame': ([c_int, POINTER(c_char_p), 
                                       POINTER(LbotPosition), POINTER(LbotEuler)], c_bool),
        'lbot_change_tool_frame': ([c_int, c_char_p], c_bool),
        'lbot_delete_tool_frame': ([c_int, c_char_p], c_bool),
        'lbot_get_all_tool_frames': ([c_int, POINTER(POINTER(c_char_p)), POINTER(c_int)], c_bool),
        'lbot_free_string_array': ([POINTER(c_char_p), c_int], None),
        
        # 工作坐标系管理
        'lbot_set_work_frame': ([c_int, c_char_p, POINTER(LbotPosition), 
                               POINTER(LbotEuler)], c_bool),
        'lbot_get_work_frame': ([c_int, c_char_p, POINTER(LbotPosition), 
                               POINTER(LbotEuler)], c_bool),
        'lbot_change_work_frame': ([c_int, c_char_p], c_bool),
        'lbot_delete_work_frame': ([c_int, c_char_p], c_bool),
        'lbot_get_all_work_frames': ([c_int, POINTER(POINTER(c_char_p)), POINTER(c_int)], c_bool),

        # 系统功能函数
        'lbot_set_zero': ([c_int], c_bool),
        'lbot_enable_arm': ([c_int, c_bool], c_bool),
        'lbot_emergency_stop': ([c_int, c_bool], c_bool),
        'lbot_clear_errors': ([], c_bool),
        
        # 工具函数
        'lbot_get_last_error': ([], c_char_p),
        'lbot_set_log_level': ([c_int], None),
    }
    
    @classmethod
    def setup_prototypes(cls, lib):
        """设置所有函数原型"""
        for func_name, (argtypes, restype) in cls.FUNCTION_PROTOTYPES.items():
            if hasattr(lib, func_name):
                func = getattr(lib, func_name)
                func.argtypes = argtypes
                if restype is not None:
                    func.restype = restype
            else:
                print(f"警告: 库中未找到函数 {func_name}")


class LbotAPI:
    """Python版本的Lbot API"""
    
    def __init__(self):
        self._lib = LibraryLoader.load_library()
        FunctionPrototypeManager.setup_prototypes(self._lib)
        self._state_callback = None
        self._error_callback = None
        self._lock = threading.RLock()
        self._function_cache = {}  # 函数缓存
    
    def _get_function(self, name):
        """获取库函数（带缓存）"""
        if name not in self._function_cache:
            if hasattr(self._lib, name):
                self._function_cache[name] = getattr(self._lib, name)
            else:
                raise AttributeError(f"函数 {name} 在库中不存在")
        return self._function_cache[name]
    
    def _call_function(self, name, *args):
        """调用库函数（带错误处理）"""
        try:
            func = self._get_function(name)
            return func(*args)
        except Exception as e:
            error_msg = f"调用函数 {name} 时出错: {e}"
            print(error_msg)
            raise RuntimeError(error_msg)
    
    def init(self, tcp_host: str) -> bool:
        """初始化API连接"""
        return self._call_function('lbot_init', tcp_host.encode('utf-8'))
    
    def cleanup(self):
        """清理资源"""
        self._call_function('lbot_cleanup')
    
    def start_state_monitor(self, state_callback: Callable[[LbotFullState], None] = None, 
                          error_callback: Callable[[int, str], None] = None) -> bool:
        """启动状态监控"""
        
        def _state_callback_wrapper(state_ptr):
            if state_callback:
                state_callback(state_ptr.contents)
        
        def _error_callback_wrapper(error_code, error_msg):
            if error_callback:
                error_callback(error_code, error_msg.decode('utf-8'))
        
        # 保存回调引用防止垃圾回收
        self._state_callback = CFUNCTYPE(None, POINTER(LbotFullState))(_state_callback_wrapper)
        self._error_callback = CFUNCTYPE(None, c_int, c_char_p)(_error_callback_wrapper)
        
        return self._call_function('lbot_start_state_monitor', self._state_callback, self._error_callback)
    
    def stop_state_monitor(self):
        """停止状态监控"""
        self._call_function('lbot_stop_state_monitor')
    
    def get_current_state(self) -> Optional[LbotFullState]:
        """获取当前状态"""
        state = LbotFullState()
        if self._call_function('lbot_get_current_state', byref(state)):
            return state
        return None
    
    # 基础运动控制
    def move_joint(self, arm: LbotArm, joints: List[float], speed: float, 
                  accel: float, block: bool = True) -> bool:
        """关节空间运动"""
        if len(joints) != 7:
            raise ValueError("关节角度数组必须包含7个元素")
        
        joints_array = (c_double * 7)(*joints)
        return self._call_function('lbot_move_joint', arm, joints_array, speed, accel, block)
    
    def move_pose(self, arm: LbotArm, position: LbotPosition, 
                 euler: LbotEuler, speed: float, accel: float, block: bool = True) -> bool:
        """笛卡尔空间点到点运动"""
        return self._call_function('lbot_move_pose', arm, byref(position), 
                                  byref(euler), speed, accel, block)
    
    def move_linear(self, arm: LbotArm, position: LbotPosition, 
                   euler: LbotEuler, speed: float, accel: float, block: bool = True) -> bool:
        """笛卡尔空间直线运动"""
        return self._call_function('lbot_move_linear', arm, byref(position), 
                                  byref(euler), speed, accel, block)
    
    
    def joint_follow(self, arm: LbotArm, joints: List[float], follow: bool = True) -> bool:
        """关节跟随控制（用于遥操作）
        
        Args:
            arm: 机械臂选择（LEFT_ARM 或 RIGHT_ARM）
            joints: 7个关节的目标角度（弧度）
            follow: 跟随模式标志：true-高跟随模式（低延迟,实时映射关节角度），false-低跟随模式（有延迟，但是机械臂跟随轨迹做了平滑处理）
        
        Returns:
            bool: 指令发送是否成功
        """
        if len(joints) != 7:
            raise ValueError("关节角度数组必须包含7个元素")
        
        joints_array = (c_double * 7)(*joints)
        return self._call_function('lbot_joint_follow', arm, joints_array, follow)
    
    # ==============================================
    # L6手控制接口
    # ==============================================
    
    def l6_set_position(self, arm: LbotArm, position: List[int]) -> bool:
        """设置L6手的位置控制
        
        Args:
            arm: 机械臂选择（LEFT_ARM 或 RIGHT_ARM）
            position: 6个手指的目标位置列表 (0~255)
        
        Returns:
            bool: 指令发送是否成功
        """
        if len(position) != 6:
            raise ValueError("位置数组必须包含6个元素")
        
        position_array = (c_uint8 * 6)(*position)
        return self._call_function('lbot_l6_set_position', arm, position_array)
    
    def l6_set_velocity(self, arm: LbotArm, velocity: List[int]) -> bool:
        """设置L6手的速度控制
        
        Args:
            arm: 机械臂选择（LEFT_ARM 或 RIGHT_ARM）
            velocity: 6个手指的目标速度列表 (0~255)
        
        Returns:
            bool: 指令发送是否成功
        """
        if len(velocity) != 6:
            raise ValueError("速度数组必须包含6个元素")
        
        velocity_array = (c_uint8 * 6)(*velocity)
        return self._call_function('lbot_l6_set_velocity', arm, velocity_array)
    
    def l6_set_effort(self, arm: LbotArm, effort: List[int]) -> bool:
        """设置L6手的力矩控制
        
        Args:
            arm: 机械臂选择（LEFT_ARM 或 RIGHT_ARM）
            effort: 6个手指的目标力矩列表 (0~255)
        
        Returns:
            bool: 指令发送是否成功
        """
        if len(effort) != 6:
            raise ValueError("力矩数组必须包含6个元素")
        
        effort_array = (c_uint8 * 6)(*effort)
        return self._call_function('lbot_l6_set_effort', arm, effort_array)
    
    # ==============================================
    # L10手控制接口 - 新增
    # ==============================================
    
    def l10_set_position(self, arm: LbotArm, position: List[int]) -> bool:
        """设置L10手的位置控制
        
        Args:
            arm: 机械臂选择（LEFT_ARM 或 RIGHT_ARM）
            position: 10个手指的目标位置列表 (0~255)
        
        Returns:
            bool: 指令发送是否成功
        """
        if len(position) != 10:
            raise ValueError("位置数组必须包含10个元素")
        
        position_array = (c_uint8 * 10)(*position)
        return self._call_function('lbot_l10_set_position', arm, position_array)
    
    def l10_set_velocity(self, arm: LbotArm, velocity: List[int]) -> bool:
        """设置L10手的速度控制
        
        Args:
            arm: 机械臂选择（LEFT_ARM 或 RIGHT_ARM）
            velocity: 10个手指的目标速度列表 (0~255)
        
        Returns:
            bool: 指令发送是否成功
        """
        if len(velocity) != 10:
            raise ValueError("速度数组必须包含10个元素")
        
        velocity_array = (c_uint8 * 10)(*velocity)
        return self._call_function('lbot_l10_set_velocity', arm, velocity_array)
    
    def l10_set_effort(self, arm: LbotArm, effort: List[int]) -> bool:
        """设置L10手的力矩控制
        
        Args:
            arm: 机械臂选择（LEFT_ARM 或 RIGHT_ARM）
            effort: 10个手指的目标力矩列表 (0~255)
        
        Returns:
            bool: 指令发送是否成功
        """
        if len(effort) != 10:
            raise ValueError("力矩数组必须包含10个元素")
        
        effort_array = (c_uint8 * 10)(*effort)
        return self._call_function('lbot_l10_set_effort', arm, effort_array)
    
    # 运动学计算
    def forward_kinematics(self, arm: LbotArm, joints: List[float]) -> tuple:
        """正运动学计算"""
        if len(joints) != 7:
            raise ValueError("关节角度数组必须包含7个元素")
        
        joints_array = (c_double * 7)(*joints)
        position = LbotPosition()
        euler = LbotEuler()
        
        success = self._call_function('lbot_forward_kinematics', arm, joints_array, byref(position), byref(euler))
        return success, position, euler
    
    def inverse_kinematics(self, arm: LbotArm, initial_joints: List[float],
                          position: LbotPosition, euler: LbotEuler) -> tuple:
        """逆运动学计算"""
        if len(initial_joints) != 7:
            raise ValueError("初始关节角度数组必须包含7个元素")
        
        initial_array = (c_double * 7)(*initial_joints)
        result_joints = (c_double * 7)()
        
        success = self._call_function('lbot_inverse_kinematics', arm, initial_array, 
                                    byref(position), byref(euler), result_joints)
        
        result_list = [result_joints[i] for i in range(7)]
        return success, result_list
    
    # 工具坐标系管理
    def set_tool_frame(self, arm: LbotArm, name: str, position: LbotPosition, 
                      euler: LbotEuler) -> bool:
        """设置工具坐标系"""
        return self._call_function('lbot_set_tool_frame', arm, name.encode('utf-8'), byref(position), byref(euler))
    
    def get_tool_frame(self, arm: LbotArm, name: str) -> tuple:
        """获取工具坐标系"""
        position = LbotPosition()
        euler = LbotEuler()
        
        success = self._call_function('lbot_get_tool_frame', arm, name.encode('utf-8'), byref(position), byref(euler))
        return success, position, euler
    
    def get_current_tool_frame(self, arm: LbotArm) -> tuple:
        """获取当前使用的工具坐标系"""
        name_ptr = c_char_p()
        position = LbotPosition()
        euler = LbotEuler()
        
        success = self._call_function('lbot_get_current_tool_frame', arm, 
                                     byref(name_ptr), byref(position), byref(euler))
        
        name = None
        if success and name_ptr.value:
            name = name_ptr.value.decode('utf-8')
            # 释放内存
            try:
                if hasattr(self._lib, 'free'):
                    self._lib.free(name_ptr)
            except:
                pass
        
        return success, name, position, euler
    
    def change_tool_frame(self, arm: LbotArm, name: str) -> bool:
        """切换工具坐标系"""
        return self._call_function('lbot_change_tool_frame', arm, name.encode('utf-8'))
    
    def delete_tool_frame(self, arm: LbotArm, name: str) -> bool:
        """删除工具坐标系"""
        return self._call_function('lbot_delete_tool_frame', arm, name.encode('utf-8'))
    
    def get_all_tool_frames(self, arm: LbotArm) -> tuple:
        """获取所有工具坐标系"""
        names_ptr = POINTER(c_char_p)()
        count = c_int()
        
        success = self._call_function('lbot_get_all_tool_frames', arm, byref(names_ptr), byref(count))
        
        if success and count.value > 0:
            names = []
            for i in range(count.value):
                if names_ptr[i]:
                    names.append(names_ptr[i].decode('utf-8'))
            self._call_function('lbot_free_string_array', names_ptr, count.value)
            return success, names
        return success, []
    
    # 工作坐标系管理
    def set_work_frame(self, arm: LbotArm, name: str, position: LbotPosition, 
                      euler: LbotEuler) -> bool:
        """设置工作坐标系"""
        return self._call_function('lbot_set_work_frame', arm, name.encode('utf-8'), byref(position), byref(euler))
    
    def get_work_frame(self, arm: LbotArm, name: str) -> tuple:
        """获取工作坐标系"""
        position = LbotPosition()
        euler = LbotEuler()
        
        success = self._call_function('lbot_get_work_frame', arm, name.encode('utf-8'), byref(position), byref(euler))
        return success, position, euler
    
    def change_work_frame(self, arm: LbotArm, name: str) -> bool:
        """切换工作坐标系"""
        return self._call_function('lbot_change_work_frame', arm, name.encode('utf-8'))
    
    def delete_work_frame(self, arm: LbotArm, name: str) -> bool:
        """删除工作坐标系"""
        return self._call_function('lbot_delete_work_frame', arm, name.encode('utf-8'))
    
    def get_all_work_frames(self, arm: LbotArm) -> tuple:
        """获取所有工作坐标系"""
        names_ptr = POINTER(c_char_p)()
        count = c_int()
        
        success = self._call_function('lbot_get_all_work_frames', arm, byref(names_ptr), byref(count))
        
        if success and count.value > 0:
            names = []
            for i in range(count.value):
                if names_ptr[i]:
                    names.append(names_ptr[i].decode('utf-8'))
            self._call_function('lbot_free_string_array', names_ptr, count.value)
            return success, names
        return success, []
    
    def get_controller_info(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """获取控制器信息
        
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: 
            (成功标志, 机器人型号, 控制器版本)
        """
        robot_model_ptr = c_char_p()
        controller_version_ptr = c_char_p()
        
        success = self._call_function('lbot_get_controller_info', 
                                    byref(robot_model_ptr), 
                                    byref(controller_version_ptr))
        
        robot_model = None
        controller_version = None
        
        if success:
            if robot_model_ptr.value:
                robot_model = robot_model_ptr.value.decode('utf-8')
            if controller_version_ptr.value:
                controller_version = controller_version_ptr.value.decode('utf-8')
            
            # 释放内存
            try:
                if hasattr(self._lib, 'free'):
                    if robot_model_ptr.value:
                        self._lib.free(robot_model_ptr)
                    if controller_version_ptr.value:
                        self._lib.free(controller_version_ptr)
            except:
                pass
        
        return success, robot_model, controller_version
    
    # 版本信息方法（如果库中有）
    def get_version_string(self) -> str:
        """获取API版本字符串"""
        try:
            if hasattr(self._lib, 'lbot_get_version_string'):
                version = self._call_function('lbot_get_version_string')
                if version:
                    return version.decode('utf-8')
        except:
            pass
        return "Unknown"

    # 系统功能
    def set_zero(self, arm: LbotArm) -> bool:
        """重新标定电机零位，设置当前位置为零位"""
        return self._call_function('lbot_set_zero', arm)
    
    def enable_arm(self, arm: LbotArm, enable: bool) -> bool:
        """使能/掉使能机械臂"""
        return self._call_function('lbot_enable_arm', arm, enable)
    
    def emergency_stop(self, arm: LbotArm, enable: bool) -> bool:
        """紧急停止/恢复"""
        return self._call_function('lbot_emergency_stop', arm, enable)
    
    def clear_errors(self) -> bool:
        """清除所有错误"""
        return self._call_function('lbot_clear_errors')
    
    # 工具函数
    def get_last_error(self) -> str:
        """获取最后一次错误信息"""
        error_msg = self._call_function('lbot_get_last_error')
        if error_msg:
            return error_msg.decode('utf-8')
        return ""
    
    def set_log_level(self, level: int):
        """设置日志级别"""
        self._call_function('lbot_set_log_level', level)
    
    # 扩展功能：动态添加新函数
    def add_function(self, name: str, argtypes: list, restype=None):
        """动态添加新函数（用于后期扩展）"""
        if hasattr(self._lib, name):
            func = getattr(self._lib, name)
            func.argtypes = argtypes
            if restype is not None:
                func.restype = restype
            self._function_cache[name] = func
            return True
        return False
    
    def list_available_functions(self) -> List[str]:
        """列出库中所有可用的函数"""
        return [name for name in dir(self._lib) if not name.startswith('_')]


# 创建全局实例和导出
try:
    api = LbotAPI()
except Exception as e:
    print(f"创建LbotAPI实例失败: {e}")
    api = None

# 导出常用枚举和结构体
__all__ = [
    'LbotArm', 'LbotMoveType', 'LbotPosition', 'LbotOrientation', 
    'LbotEuler', 'LbotArmState', 'LbotFullState', 'api',
    'LbotAPI', 'LbotConfig'
]