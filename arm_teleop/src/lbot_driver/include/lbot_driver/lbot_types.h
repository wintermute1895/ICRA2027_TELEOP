/**
 * @file lbot_types.h
 * @brief 该文件定义了结构和枚举定义
 * @author 李亚慧
 * @date 2025.1.19
 * @copyright 灵心巧手科技有限公司
 */
#ifndef LBOT_TYPES_H
#define LBOT_TYPES_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>


// 机械臂类型枚举
typedef enum {
    LBOT_LEFT_ARM = 0,
    LBOT_RIGHT_ARM = 1
} lbot_arm_t;

// 机械臂控制句柄
typedef struct {
    uint64_t id;         // 句柄ID，连接成功返回>0的值，0表示无效句柄
}lbot_handle_t;

// 运动类型枚举
typedef enum {
    LBOT_MOVE_JOINT = 0,      // 关节空间运动
    LBOT_MOVE_POSE = 1,       // 笛卡尔空间点到点
    LBOT_MOVE_LINEAR = 2      // 笛卡尔空间直线运动
} lbot_move_type_t;

// 坐标系结构体
typedef struct {
    double x, y, z;
} lbot_position_t;

typedef struct {
    double x, y, z, w;
} lbot_orientation_t;

typedef struct {
    double x, y, z;
} lbot_euler_t;

// 关节状态结构体
typedef struct {
    // 关节数据
    char name[7][32];         // 7个关节名称
    double joint_position[7]; // 7个关节位置
    double velocity[7];       // 7个关节速度
    double effort[7];         // 7个关节力矩
    
    // 时间戳
    int32_t sec;              // 秒
    uint32_t nanosec;         // 纳秒
    char frame_id[64];        // 工作坐标系
    
    // 末端状态
    lbot_position_t end_effector_position; // 末端位置
    lbot_euler_t euler;                    // 欧拉角
    lbot_orientation_t orientation;        // 四元数姿态
} lbot_arm_state_t;

// 机械臂完整状态结构体
typedef struct {
    lbot_arm_state_t left_arm;
    lbot_arm_state_t right_arm;
    uint64_t system_timestamp; // 系统时间戳（纳秒）
    char arm_ip[16];           // 机械臂IP地址
} lbot_full_state_t;

// 回调函数类型定义
typedef void (*lbot_state_callback_t)(const lbot_full_state_t* state);
typedef void (*lbot_error_callback_t)(int error_code, const char* error_msg);

#ifdef __cplusplus
}
#endif

#endif // LBOT_TYPES_H