#ifndef LINKER_ARM_H
#define LINKER_ARM_H

#include <thread>
#include <mutex>
#include <queue>
#include <chrono>
#include <iostream>
#include <sstream>
#include <condition_variable>
#include <cmath>
#include "CanBus.h"

#define RECV_DEBUG 0

namespace LinkerArm
{

typedef enum
{									  
    GET_JOINT_POSITION_1 = 0x02,
    GET_JOINT_POSITION_2 = 0x03,
    GET_JOINT_POSITION = 0x04,
    LEFT_JOINT_POSITION_1 = 0x65,
    LEFT_JOINT_POSITION_2 = 0x66,
    RIGHT_JOINT_POSITION_1 = 0x67,
    RIGHT_JOINT_POSITION_2 = 0x68,
    RESET_ZERO_COMMAND_1 = 0xC0,
    RESET_ZERO_COMMAND_2 = 0xC1,
    LINKER_HAND_VERSION = 0x64,

}FRAME_PROPERTY;

class LinkerArm
{
public:
    LinkerArm(const std::string device_type);
    LinkerArm(const std::string &canChannel, int baudrate);
    ~LinkerArm();
    
    std::vector<float> getJointPosition();
    std::vector<bool> getJointErrorCode();
    std::string getVersion();
    std::string getCanInterface() const { return bus->getInterface(); }
    void resetZero(const uint8_t joint = 0xFF);
    
    
    
    void printJointInfo();

private:
    void receiveResponse();
    
    std::string getCurrentTime();
    
    float bytesToInt16(const uint8_t hi, const uint8_t lo) {
        std::uint16_t u = (static_cast<std::uint16_t>(hi) << 8) | lo;
        return static_cast<std::int16_t>(u) / 10.0;
    }
    
    float bytesToInt16(const float last_position, const uint8_t hi, const uint8_t lo) {
        std::uint16_t u = (static_cast<std::uint16_t>(hi) << 8) | lo;
        
        float raw = int16_t(u) / 10.0f;

        raw = std::fmod(raw + 180.0f, 360.0f);
        if (raw < 0) raw += 360.0f;
        raw -= 180.0f;

        float delta = raw - last_position;
        
        // 如果是首次读取（last_position 为 0），直接使用新值
        if (std::fabs(last_position) < 0.01f) {
            return std::round(raw * 10.0f) / 10.0f;
        }
        
        // 跳变过滤：超过阈值时使用上一次的值，避免抖动
        if (std::fabs(delta) >= 90.0f) {
            return last_position;
        }

        return std::round(raw * 10.0f) / 10.0f;
    }
    
private:
    uint32_t cid;
    std::unique_ptr<Communication::CanBus> bus;
    std::thread receiveThread;
    std::atomic<bool> running{true};
    std::vector<float> joint_position;
    std::vector<bool> joint_error_code;
	std::vector<uint8_t> version;
    std::mutex err_mtx;
    std::mutex pos_mtx;
};
} // namespace LinkerArm
#endif // LINKER_ARM_H
