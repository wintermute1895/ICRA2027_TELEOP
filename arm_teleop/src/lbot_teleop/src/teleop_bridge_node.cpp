// Copyright (c) 2025 LinkerRobot Tech
//
// LBot Teleoperation Bridge Node
// 遥操作桥接节点 - 将主臂(linkerta)数据转发到从臂(lbot_driver)
//
// 功能：
// 1. 订阅主臂关节数据
// 2. 单位转换（度 -> 弧度）
// 3. 关节映射与缩放
// 4. 安全限位检查
// 5. 发布到从臂关节跟随话题
// 6. 首次运动使用 MoveJ 服务平滑移动到初始位置

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/joint_state.hpp>
#include <lbot_arm_interfaces/msg/follow_joint.hpp>
#include <lbot_arm_interfaces/srv/move_j.hpp>
#include <cmath>
#include <algorithm>
#include <functional>
#include <map>

class TeleopBridgeNode : public rclcpp::Node
{
public:
    TeleopBridgeNode() : Node("teleop_bridge_node")
    {
        // 声明参数
        declare_parameters();
        
        // 获取参数
        load_parameters();
        
        // 为每个从臂创建发布器和服务客户端
        for (const auto& ns : slave_namespaces_) {
            // 创建发布器
            left_follow_pubs_[ns] = this->create_publisher<lbot_arm_interfaces::msg::FollowJoint>(
                "/" + ns + "/left_arm/joint_follow", 10);
            right_follow_pubs_[ns] = this->create_publisher<lbot_arm_interfaces::msg::FollowJoint>(
                "/" + ns + "/right_arm/joint_follow", 10);

            // 创建 MoveJ 服务客户端（用于首次平滑移动）
            left_movej_clients_[ns] = this->create_client<lbot_arm_interfaces::srv::MoveJ>(
                "/" + ns + "/left_arm/move_joint");
            right_movej_clients_[ns] = this->create_client<lbot_arm_interfaces::srv::MoveJ>(
                "/" + ns + "/right_arm/move_joint");
            
            // 初始化首次运动标志
            left_first_move_done_[ns] = false;
            right_first_move_done_[ns] = false;
            left_first_move_in_progress_[ns] = false;
            right_first_move_in_progress_[ns] = false;
            
            RCLCPP_INFO(this->get_logger(), "Created publishers and clients for namespace: %s", ns.c_str());
        }

        // 创建订阅器（只订阅一次主臂话题）
        left_joint_sub_ = this->create_subscription<sensor_msgs::msg::JointState>(
            master_left_topic_, 10,
            std::bind(&TeleopBridgeNode::left_joint_callback, this, std::placeholders::_1));
        right_joint_sub_ = this->create_subscription<sensor_msgs::msg::JointState>(
            master_right_topic_, 10,
            std::bind(&TeleopBridgeNode::right_joint_callback, this, std::placeholders::_1));

        print_config();
        
        RCLCPP_INFO(this->get_logger(), "Teleop Bridge Node initialized successfully");
    }

private:
    // 角度转弧度常量
    static constexpr double DEG_TO_RAD = M_PI / 180.0;

    void declare_parameters()
    {
        // 话题配置
        this->declare_parameter<std::string>("master_left_topic", "/left_arm_joint_control");
        this->declare_parameter<std::string>("master_right_topic", "/right_arm_joint_control");
        this->declare_parameter<std::vector<std::string>>("slave_namespaces", std::vector<std::string>{"robot1"});
        
        // 转换配置
        this->declare_parameter<double>("scale_factor", 1.0);
        this->declare_parameter<bool>("follow_mode", true);
        this->declare_parameter<std::string>("robot_type", "LS");
        this->declare_parameter<std::vector<int64_t>>(
            "negation", {1, 1, 1, -1, 1, -1, -1, 1, 1, 1, 1, 1, -1, -1});
        
        // 首次移动配置
        this->declare_parameter<double>("first_move_speed", 0.5);
        this->declare_parameter<double>("first_move_acce", 0.5);
        
        // 使能配置
        this->declare_parameter<bool>("enable_left_arm", true);
        this->declare_parameter<bool>("enable_right_arm", true);
        
        // 关节映射 (主臂关节索引 -> 从臂关节索引)
        this->declare_parameter<std::vector<int64_t>>("left_joint_mapping", {0, 1, 2, 3, 4, 5, 6});
        this->declare_parameter<std::vector<int64_t>>("right_joint_mapping", {0, 1, 2, 3, 4, 5, 6});
        
        // 安全限位 (弧度) - 左臂
        this->declare_parameter<std::vector<double>>("left_joint_limits_min", 
            {-3.14, -2.0, -3.14, -2.0, -3.14, -2.0, -3.14});
        this->declare_parameter<std::vector<double>>("left_joint_limits_max", 
            {3.14, 2.0, 3.14, 2.0, 3.14, 2.0, 3.14});
        
        // 安全限位 (弧度) - 右臂
        this->declare_parameter<std::vector<double>>("right_joint_limits_min", 
            {-3.14, -2.0, -3.14, -2.0, -3.14, -2.0, -3.14});
        this->declare_parameter<std::vector<double>>("right_joint_limits_max", 
            {3.14, 2.0, 3.14, 2.0, 3.14, 2.0, 3.14});
        
        this->declare_parameter<bool>("enable_joint_limits", false);
    }

    void load_parameters()
    {
        master_left_topic_ = this->get_parameter("master_left_topic").as_string();
        master_right_topic_ = this->get_parameter("master_right_topic").as_string();
        slave_namespaces_ = this->get_parameter("slave_namespaces").as_string_array();
        
        // 兼容旧配置：如果 slave_namespaces 为空，尝试读取 slave_namespace
        if (slave_namespaces_.empty()) {
            this->declare_parameter<std::string>("slave_namespace", "robot1");
            slave_namespaces_.push_back(this->get_parameter("slave_namespace").as_string());
        }
        
        scale_factor_ = this->get_parameter("scale_factor").as_double();
        follow_mode_ = this->get_parameter("follow_mode").as_bool();
    robot_type_ = this->get_parameter("robot_type").as_string();

        auto negation_param = this->get_parameter("negation").as_integer_array();
        negation_.assign(negation_param.begin(), negation_param.end());
        left_negation_.assign(7, 1);
        right_negation_.assign(7, 1);
        if (negation_.size() >= 14) {
            left_negation_.assign(negation_.begin(), negation_.begin() + 7);
            right_negation_.assign(negation_.begin() + 7, negation_.begin() + 14);
        } else if (negation_.size() >= 7) {
            left_negation_.assign(negation_.begin(), negation_.begin() + 7);
            right_negation_.assign(negation_.begin(), negation_.begin() + 7);
        } else if (!negation_.empty()) {
            RCLCPP_WARN(this->get_logger(), "Negation param size=%zu, expected >=7, using default +1", negation_.size());
        }
        
        first_move_speed_ = this->get_parameter("first_move_speed").as_double();
        first_move_acce_ = this->get_parameter("first_move_acce").as_double();
        
        enable_left_arm_ = this->get_parameter("enable_left_arm").as_bool();
        enable_right_arm_ = this->get_parameter("enable_right_arm").as_bool();
        
        auto left_mapping = this->get_parameter("left_joint_mapping").as_integer_array();
        auto right_mapping = this->get_parameter("right_joint_mapping").as_integer_array();
        left_joint_mapping_.assign(left_mapping.begin(), left_mapping.end());
        right_joint_mapping_.assign(right_mapping.begin(), right_mapping.end());
        
        enable_joint_limits_ = this->get_parameter("enable_joint_limits").as_bool();

        // 先根据 robot_type 设置默认值
        if (robot_type_ == "LS") {
            left_joint_limits_min_ = {-2.9, -0.15, -2.35, 0.0, -2.35, -1.57, -1.57};
            left_joint_limits_max_ = {1.0, 3.14, 2.35, 2.2, 2.35, 1.57, 1.57};
            right_joint_limits_min_ = {-1.0, -3.14, -2.35, 0.0, -2.35, -1.57, -1.57};
            right_joint_limits_max_ = {2.9, 0.15, 2.35, 2.2, 2.35, 1.57, 1.57};
            left_negation_ = {1, 1, 1, -1, 1, -1, 1};
            right_negation_ = {1, 1, 1, 1, 1, -1, 1};
        } else if (robot_type_ == "RS") {
            left_joint_limits_min_ = {-2.1, -2.967, -2.2, -0.785, -2.9, -1.57, -1.57};
            left_joint_limits_max_ = {3.7, 0.148, 2.2, 1.7, 2.9, 1.57, 1.57};
            right_joint_limits_min_ = {-3.7, -0.148, -2.2, -1.7, -2.9, -1.57, -1.57};
            right_joint_limits_max_ = {2.1, 2.967, 2.2, 0.785, 2.9, 1.57, 1.57};
            left_negation_ = {-1, -1, -1, -1, -1, -1, -1};
            right_negation_ = {-1, -1, -1, -1, -1, -1, -1};
        } else {
            RCLCPP_WARN(this->get_logger(), "Unknown robot_type '%s', using configured limits/negation", robot_type_.c_str());
        }

        // 再用配置文件中的值覆盖（如果用户在配置文件中显式设置了这些参数）
        // 这样配置文件的优先级高于 robot_type 的硬编码默认值
        auto cfg_left_min = this->get_parameter("left_joint_limits_min").as_double_array();
        auto cfg_left_max = this->get_parameter("left_joint_limits_max").as_double_array();
        auto cfg_right_min = this->get_parameter("right_joint_limits_min").as_double_array();
        auto cfg_right_max = this->get_parameter("right_joint_limits_max").as_double_array();

        // 判断是否与 declare 时的默认值不同，不同说明用户在配置文件中设置了
        std::vector<double> default_limits_min = {-3.14, -2.0, -3.14, -2.0, -3.14, -2.0, -3.14};
        std::vector<double> default_limits_max = {3.14, 2.0, 3.14, 2.0, 3.14, 2.0, 3.14};
        if (cfg_left_min != default_limits_min) left_joint_limits_min_ = cfg_left_min;
        if (cfg_left_max != default_limits_max) left_joint_limits_max_ = cfg_left_max;
        if (cfg_right_min != default_limits_min) right_joint_limits_min_ = cfg_right_min;
        if (cfg_right_max != default_limits_max) right_joint_limits_max_ = cfg_right_max;
    }

    void print_config()
    {
        RCLCPP_INFO(this->get_logger(), "========== Teleop Bridge Configuration ==========");
        RCLCPP_INFO(this->get_logger(), "Master left topic:  %s", master_left_topic_.c_str());
        RCLCPP_INFO(this->get_logger(), "Master right topic: %s", master_right_topic_.c_str());
        std::string ns_list;
        for (const auto& ns : slave_namespaces_) {
            ns_list += ns + " ";
        }
        RCLCPP_INFO(this->get_logger(), "Slave namespaces:   %s", ns_list.c_str());
        RCLCPP_INFO(this->get_logger(), "Scale factor:       %.2f", scale_factor_);
        RCLCPP_INFO(this->get_logger(), "Follow mode:        %s", follow_mode_ ? "true" : "false");
    RCLCPP_INFO(this->get_logger(), "Robot type:         %s", robot_type_.c_str());
        RCLCPP_INFO(this->get_logger(), "Left arm enabled:   %s", enable_left_arm_ ? "true" : "false");
        RCLCPP_INFO(this->get_logger(), "Right arm enabled:  %s", enable_right_arm_ ? "true" : "false");
        RCLCPP_INFO(this->get_logger(), "Joint limits:       %s", enable_joint_limits_ ? "enabled" : "disabled");
        RCLCPP_INFO(this->get_logger(), "First move speed:   %.2f", first_move_speed_);
        RCLCPP_INFO(this->get_logger(), "First move acce:    %.2f", first_move_acce_);
        RCLCPP_INFO(this->get_logger(), "=================================================");
    }

    // 处理关节数据：映射、转换、限位
    std::vector<float> process_joints(
        const std::vector<double>& input_joints,
        const std::vector<int>& mapping,
        const std::vector<int>& negation,
        const std::vector<double>& limits_min,
        const std::vector<double>& limits_max)
    {
        std::vector<float> output_joints;
        output_joints.reserve(mapping.size());

        for (size_t i = 0; i < mapping.size(); ++i) {
            int src_idx = mapping[i];
            
            // 检查源索引有效性
            if (src_idx < 0 || src_idx >= static_cast<int>(input_joints.size())) {
                output_joints.push_back(0.0f);
                continue;
            }

            double value = input_joints[src_idx];

            // 方向修正
            if (i < negation.size()) {
                value *= static_cast<double>(negation[i]);
            }

            // 角度转弧度 (主臂发送角度，从臂接收弧度)
            value *= DEG_TO_RAD;

            // 缩放
            value *= scale_factor_;

            // 安全限位
            if (enable_joint_limits_ && i < limits_min.size() && i < limits_max.size()) {
                value = std::clamp(value, limits_min[i], limits_max[i]);
            }

            output_joints.push_back(static_cast<float>(value));
        }

        return output_joints;
    }

    // 调用 MoveJ 服务进行首次平滑移动（异步）
    void call_movej_service_async(
        rclcpp::Client<lbot_arm_interfaces::srv::MoveJ>::SharedPtr client,
        const std::vector<float>& joints,
        const std::string& arm_name,
        const std::string& ns,
        const std::function<void(bool)>& done_cb)
    {
        if (!client->wait_for_service(std::chrono::milliseconds(100))) {
            RCLCPP_WARN(this->get_logger(), "[%s/%s] MoveJ service not available, skipping first move", ns.c_str(), arm_name.c_str());
            done_cb(false);
            return;
        }

        auto request = std::make_shared<lbot_arm_interfaces::srv::MoveJ::Request>();
        request->joints = joints;
        request->speed = static_cast<float>(first_move_speed_);
        request->acce = static_cast<float>(first_move_acce_);
        request->block = true;  // 阻塞等待完成

        RCLCPP_INFO(this->get_logger(), "[%s/%s] First move: calling MoveJ to initial position...", ns.c_str(), arm_name.c_str());

        client->async_send_request(
            request,
            [this, arm_name, ns, done_cb](rclcpp::Client<lbot_arm_interfaces::srv::MoveJ>::SharedFuture future) {
                auto result = future.get();
                if (result->success) {
                    RCLCPP_INFO(this->get_logger(), "[%s/%s] First move completed, switching to follow mode", ns.c_str(), arm_name.c_str());
                    done_cb(true);
                } else {
                    RCLCPP_WARN(this->get_logger(), "[%s/%s] First move failed", ns.c_str(), arm_name.c_str());
                    done_cb(false);
                }
            }
        );
    }

    void left_joint_callback(const sensor_msgs::msg::JointState::SharedPtr msg)
    {
        if (!enable_left_arm_ || msg->position.empty()) return;

        auto joints = process_joints(msg->position, left_joint_mapping_, left_negation_,
                                     left_joint_limits_min_, left_joint_limits_max_);

        // 向所有从臂发送
        for (const auto& ns : slave_namespaces_) {
            // 首次运动：使用 MoveJ 服务平滑移动到初始位置
            if (!left_first_move_done_[ns]) {
                if (left_first_move_in_progress_[ns]) {
                    continue;
                }
                left_first_move_in_progress_[ns] = true;
                call_movej_service_async(left_movej_clients_[ns], joints, "left_arm", ns,
                    [this, ns](bool success) {
                        left_first_move_done_[ns] = success;
                        left_first_move_in_progress_[ns] = false;
                    });
                continue;
            }

            // 正常跟随模式
            auto follow_msg = lbot_arm_interfaces::msg::FollowJoint();
            follow_msg.joints = joints;
            follow_msg.follow = follow_mode_;

            left_follow_pubs_[ns]->publish(follow_msg);
        }
    }

    void right_joint_callback(const sensor_msgs::msg::JointState::SharedPtr msg)
    {
        if (!enable_right_arm_ || msg->position.empty()) return;

        auto joints = process_joints(msg->position, right_joint_mapping_, right_negation_,
                                     right_joint_limits_min_, right_joint_limits_max_);

        // 向所有从臂发送
        for (const auto& ns : slave_namespaces_) {
            // 首次运动：使用 MoveJ 服务平滑移动到初始位置
            if (!right_first_move_done_[ns]) {
                if (right_first_move_in_progress_[ns]) {
                    continue;
                }
                right_first_move_in_progress_[ns] = true;
                call_movej_service_async(right_movej_clients_[ns], joints, "right_arm", ns,
                    [this, ns](bool success) {
                        right_first_move_done_[ns] = success;
                        right_first_move_in_progress_[ns] = false;
                    });
                continue;
            }

            // 正常跟随模式
            auto follow_msg = lbot_arm_interfaces::msg::FollowJoint();
            follow_msg.joints = joints;
            follow_msg.follow = follow_mode_;

            right_follow_pubs_[ns]->publish(follow_msg);
        }
    }

    // 参数
    std::string master_left_topic_;
    std::string master_right_topic_;
    std::vector<std::string> slave_namespaces_;
    
    double scale_factor_;
    bool follow_mode_;
    std::string robot_type_;
    std::vector<int> negation_;
    std::vector<int> left_negation_;
    std::vector<int> right_negation_;
    
    double first_move_speed_;
    double first_move_acce_;
    
    bool enable_left_arm_;
    bool enable_right_arm_;
    
    // 首次运动标志 (每个从臂独立)
    std::map<std::string, bool> left_first_move_done_;
    std::map<std::string, bool> right_first_move_done_;
    std::map<std::string, bool> left_first_move_in_progress_;
    std::map<std::string, bool> right_first_move_in_progress_;
    
    std::vector<int> left_joint_mapping_;
    std::vector<int> right_joint_mapping_;
    
    std::vector<double> left_joint_limits_min_;
    std::vector<double> left_joint_limits_max_;
    std::vector<double> right_joint_limits_min_;
    std::vector<double> right_joint_limits_max_;
    bool enable_joint_limits_;

    // 发布器 (每个从臂一个)
    std::map<std::string, rclcpp::Publisher<lbot_arm_interfaces::msg::FollowJoint>::SharedPtr> left_follow_pubs_;
    std::map<std::string, rclcpp::Publisher<lbot_arm_interfaces::msg::FollowJoint>::SharedPtr> right_follow_pubs_;

    // MoveJ 服务客户端 (每个从臂一个)
    std::map<std::string, rclcpp::Client<lbot_arm_interfaces::srv::MoveJ>::SharedPtr> left_movej_clients_;
    std::map<std::string, rclcpp::Client<lbot_arm_interfaces::srv::MoveJ>::SharedPtr> right_movej_clients_;

    // 订阅器 (只有一个，订阅主臂)
    rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr left_joint_sub_;
    rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr right_joint_sub_;
};

int main(int argc, char *argv[])
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<TeleopBridgeNode>();
    RCLCPP_INFO(node->get_logger(), "Teleop Bridge Node spinning...");
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
