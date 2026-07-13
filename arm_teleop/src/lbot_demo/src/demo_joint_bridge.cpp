// Copyright (c) 2025 LinkerRobot Tech
//
// 关节数据桥接节点
// 订阅 linkerta 的关节数据，转发到 lbot_driver 的关节跟随话题

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/joint_state.hpp>
#include <lbot_arm_interfaces/msg/follow_joint.hpp>
#include <cmath>

class JointBridgeNode : public rclcpp::Node
{
public:
    JointBridgeNode() : Node("joint_bridge_node")
    {
        // 声明参数
        this->declare_parameter<std::string>("robot_namespace", "robot1");
        this->declare_parameter<bool>("follow_mode", true);
        this->declare_parameter<bool>("convert_to_radians", true);  // 是否转换为弧度
        
        robot_ns_ = this->get_parameter("robot_namespace").as_string();
        follow_mode_ = this->get_parameter("follow_mode").as_bool();
        convert_to_radians_ = this->get_parameter("convert_to_radians").as_bool();

        // 创建发布器 - 发布到 lbot_driver 的关节跟随话题
        left_follow_pub_ = this->create_publisher<lbot_arm_interfaces::msg::FollowJoint>(
            "/" + robot_ns_ + "/left_arm/joint_follow", 10);
        right_follow_pub_ = this->create_publisher<lbot_arm_interfaces::msg::FollowJoint>(
            "/" + robot_ns_ + "/right_arm/joint_follow", 10);

        // 创建订阅器 - 订阅 linkerta 的关节数据
        left_joint_sub_ = this->create_subscription<sensor_msgs::msg::JointState>(
            "/left_arm_joint_control", 10,
            std::bind(&JointBridgeNode::left_joint_callback, this, std::placeholders::_1));
        right_joint_sub_ = this->create_subscription<sensor_msgs::msg::JointState>(
            "/right_arm_joint_control", 10,
            std::bind(&JointBridgeNode::right_joint_callback, this, std::placeholders::_1));

        RCLCPP_INFO(this->get_logger(), "Joint Bridge Node initialized");
        RCLCPP_INFO(this->get_logger(), "  Robot namespace: %s", robot_ns_.c_str());
        RCLCPP_INFO(this->get_logger(), "  Follow mode: %s", follow_mode_ ? "true" : "false");
        RCLCPP_INFO(this->get_logger(), "  Convert to radians: %s", convert_to_radians_ ? "true (deg->rad)" : "false (pass-through)");
        RCLCPP_INFO(this->get_logger(), "  Subscribing: /left_arm_joint_control -> /%s/left_arm/joint_follow", robot_ns_.c_str());
        RCLCPP_INFO(this->get_logger(), "  Subscribing: /right_arm_joint_control -> /%s/right_arm/joint_follow", robot_ns_.c_str());
    }

private:
    // 角度转弧度
    static constexpr double DEG_TO_RAD = M_PI / 180.0;

    void left_joint_callback(const sensor_msgs::msg::JointState::SharedPtr msg)
    {
        if (msg->position.empty()) return;

        auto follow_msg = lbot_arm_interfaces::msg::FollowJoint();
        
        // 复制关节数据
        follow_msg.joints.resize(msg->position.size());
        for (size_t i = 0; i < msg->position.size(); ++i) {
            if (convert_to_radians_) {
                // linkerta 输出角度(度)，转换为弧度
                follow_msg.joints[i] = static_cast<float>(msg->position[i] * DEG_TO_RAD);
            } else {
                follow_msg.joints[i] = static_cast<float>(msg->position[i]);
            }
        }
        follow_msg.follow = follow_mode_;

        left_follow_pub_->publish(follow_msg);
    }

    void right_joint_callback(const sensor_msgs::msg::JointState::SharedPtr msg)
    {
        if (msg->position.empty()) return;

        auto follow_msg = lbot_arm_interfaces::msg::FollowJoint();
        
        // 复制关节数据
        follow_msg.joints.resize(msg->position.size());
        for (size_t i = 0; i < msg->position.size(); ++i) {
            if (convert_to_radians_) {
                // linkerta 输出角度(度)，转换为弧度
                follow_msg.joints[i] = static_cast<float>(msg->position[i] * DEG_TO_RAD);
            } else {
                follow_msg.joints[i] = static_cast<float>(msg->position[i]);
            }
        }
        follow_msg.follow = follow_mode_;

        right_follow_pub_->publish(follow_msg);
    }

    // 参数
    std::string robot_ns_;
    bool follow_mode_;
    bool convert_to_radians_;

    // 发布器
    rclcpp::Publisher<lbot_arm_interfaces::msg::FollowJoint>::SharedPtr left_follow_pub_;
    rclcpp::Publisher<lbot_arm_interfaces::msg::FollowJoint>::SharedPtr right_follow_pub_;

    // 订阅器
    rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr left_joint_sub_;
    rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr right_joint_sub_;
};

int main(int argc, char *argv[])
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<JointBridgeNode>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
