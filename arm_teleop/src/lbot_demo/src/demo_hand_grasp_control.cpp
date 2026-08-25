#include <algorithm>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "std_msgs/msg/u_int8.hpp"
#include "std_msgs/msg/u_int8_multi_array.hpp"

namespace
{
using Array = std_msgs::msg::UInt8MultiArray;

std::vector<uint8_t> to_u8(const std::vector<int64_t> &values, std::size_t expected,
                           const std::string &name)
{
  if (values.size() != expected) {
    throw std::runtime_error(name + " must contain " + std::to_string(expected) + " values");
  }
  std::vector<uint8_t> result;
  result.reserve(expected);
  for (const auto value : values) {
    if (value < 0 || value > 255) {
      throw std::runtime_error(name + " values must be in [0, 255]");
    }
    result.push_back(static_cast<uint8_t>(value));
  }
  return result;
}

Array make_array(const std::vector<uint8_t> &values)
{
  Array message;
  message.data = values;
  return message;
}
}  // namespace

class HandGraspNode : public rclcpp::Node
{
public:
  HandGraspNode()
  : Node("hand_grasp_control")
  {
    declare_parameter<std::string>("robot_namespace", "robot1");
    declare_parameter<std::string>("hand_type", "l10");
    declare_parameter<std::string>("side", "both");
    declare_parameter<std::string>("state_topic", "hand/grasp_state");
    declare_parameter<std::string>("gesture_topic", "hand/gesture");
    declare_parameter<std::string>("gesture", "");
    declare_parameter<int64_t>("state", 0);
    declare_parameter<int64_t>("speed", 250);
    declare_parameter<int64_t>("force", 250);

    // The defaults match the SDK examples in demo_hand_l6/l10_control.cpp.
    declare_parameter<std::vector<int64_t>>("l6_open", {128, 128, 128, 128, 128, 128});
    declare_parameter<std::vector<int64_t>>("l6_pregrasp", {190, 190, 190, 190, 190, 190});
    declare_parameter<std::vector<int64_t>>("l6_grasp", {250, 250, 250, 250, 250, 250});
    declare_parameter<std::vector<int64_t>>(
      "l10_open", {250, 128, 250, 250, 250, 250, 128, 128, 128, 250});
    declare_parameter<std::vector<int64_t>>(
      "l10_pregrasp", {175, 128, 145, 145, 145, 145, 128, 128, 128, 230});
    declare_parameter<std::vector<int64_t>>(
      "l10_grasp", {100, 128, 10, 10, 10, 10, 128, 128, 128, 250});
    // Optional user-defined gestures. Positions are flattened row-major:
    // [gesture_0 joint_0..N, gesture_1 joint_0..N, ...].
    declare_parameter<std::vector<std::string>>("gesture_names", std::vector<std::string>{});
    declare_parameter<std::vector<int64_t>>("gesture_positions", std::vector<int64_t>{});

    robot_namespace_ = get_parameter("robot_namespace").as_string();
    hand_type_ = get_parameter("hand_type").as_string();
    side_ = get_parameter("side").as_string();
    const auto state_topic = get_parameter("state_topic").as_string();
    const auto gesture_topic = get_parameter("gesture_topic").as_string();
    if (hand_type_ != "l6" && hand_type_ != "l10") {
      throw std::runtime_error("hand_type must be l6 or l10");
    }
    if (side_ != "left" && side_ != "right" && side_ != "both") {
      throw std::runtime_error("side must be left, right, or both");
    }

    const std::size_t count = hand_type_ == "l6" ? 6 : 10;
    const std::string prefix = hand_type_ == "l6" ? "l6_" : "l10_";
    positions_[0] = to_u8(get_parameter(prefix + "open").as_integer_array(), count, prefix + "open");
    positions_[1] = to_u8(
      get_parameter(prefix + "pregrasp").as_integer_array(), count, prefix + "pregrasp");
    positions_[2] = to_u8(get_parameter(prefix + "grasp").as_integer_array(), count, prefix + "grasp");
    gestures_["open"] = positions_[0];
    gestures_["pregrasp"] = positions_[1];
    gestures_["grasp"] = positions_[2];
    load_custom_gestures(
      get_parameter("gesture_names").as_string_array(),
      get_parameter("gesture_positions").as_integer_array(), count);

    const auto speed = checked_fill(get_parameter("speed").as_int(), count, "speed");
    const auto force = checked_fill(get_parameter("force").as_int(), count, "force");
    speed_values_ = speed;
    force_values_ = force;
    if (side_ == "left" || side_ == "both") {
      left_joint_pub_ = make_publisher("left");
      left_speed_pub_ = make_publisher("left", "speed");
      left_force_pub_ = make_publisher("left", "force");
    }
    if (side_ == "right" || side_ == "both") {
      right_joint_pub_ = make_publisher("right");
      right_speed_pub_ = make_publisher("right", "speed");
      right_force_pub_ = make_publisher("right", "force");
    }

    state_sub_ = create_subscription<std_msgs::msg::UInt8>(
      state_topic, 10,
      std::bind(&HandGraspNode::state_callback, this, std::placeholders::_1));
    gesture_sub_ = create_subscription<std_msgs::msg::String>(
      gesture_topic, 10,
      std::bind(&HandGraspNode::gesture_callback, this, std::placeholders::_1));
    RCLCPP_INFO(get_logger(), "Hand grasp control ready: type=%s side=%s state_topic=%s gesture_topic=%s",
                hand_type_.c_str(), side_.c_str(), state_topic.c_str(), gesture_topic.c_str());

    // Publish after discovery has had time to match the driver subscriptions.
    startup_timer_ = create_wall_timer(
      std::chrono::milliseconds(500), [this]() {
        startup_timer_->cancel();
        if (left_speed_pub_) left_speed_pub_->publish(make_array(speed_values_));
        if (left_force_pub_) left_force_pub_->publish(make_array(force_values_));
        if (right_speed_pub_) right_speed_pub_->publish(make_array(speed_values_));
        if (right_force_pub_) right_force_pub_->publish(make_array(force_values_));
        const auto initial_gesture = get_parameter("gesture").as_string();
        if (initial_gesture.empty()) {
          publish_state(get_parameter("state").as_int(), true);
        } else {
          publish_gesture(initial_gesture, true);
        }
      });
  }

private:
  std::vector<uint8_t> checked_fill(int64_t value, std::size_t count, const std::string &name)
  {
    if (value < 0 || value > 255) {
      throw std::runtime_error(name + " must be in [0, 255]");
    }
    return std::vector<uint8_t>(count, static_cast<uint8_t>(value));
  }

  rclcpp::Publisher<Array>::SharedPtr make_publisher(const std::string &side,
                                                       const std::string &kind = "joint")
  {
    const std::string topic = "/" + robot_namespace_ + "/" + side + "_hand/set_" +
      hand_type_ + "_" + kind;
    return create_publisher<Array>(topic, 10);
  }

  void state_callback(const std_msgs::msg::UInt8::ConstSharedPtr message)
  {
    publish_state(message->data, false);
  }

  void gesture_callback(const std_msgs::msg::String::ConstSharedPtr message)
  {
    publish_gesture(message->data, false);
  }

  void load_custom_gestures(const std::vector<std::string> &names,
                            const std::vector<int64_t> &flat_positions, std::size_t count)
  {
    if (names.empty()) {
      if (!flat_positions.empty()) {
        throw std::runtime_error("gesture_positions requires gesture_names");
      }
      return;
    }
    if (flat_positions.size() != names.size() * count) {
      throw std::runtime_error(
        "gesture_positions must contain gesture_names.size() * joint_count values");
    }
    for (std::size_t i = 0; i < names.size(); ++i) {
      if (names[i].empty() || gestures_.count(names[i]) != 0) {
        throw std::runtime_error("gesture_names must be non-empty and unique: " + names[i]);
      }
      std::vector<int64_t> values(
        flat_positions.begin() + static_cast<std::ptrdiff_t>(i * count),
        flat_positions.begin() + static_cast<std::ptrdiff_t>((i + 1) * count));
      gestures_[names[i]] = to_u8(values, count, "gesture_positions");
    }
  }

  void publish_gesture(const std::string &name, bool startup)
  {
    const auto it = gestures_.find(name);
    if (it == gestures_.end()) {
      RCLCPP_WARN(get_logger(), "Unknown gesture '%s'; available gestures: open, pregrasp, grasp",
                  name.c_str());
      return;
    }
    const auto message = make_array(it->second);
    if (left_joint_pub_) left_joint_pub_->publish(message);
    if (right_joint_pub_) right_joint_pub_->publish(message);
    RCLCPP_INFO(get_logger(), "%s gesture '%s'", startup ? "Initial" : "Set", name.c_str());
  }

  void publish_state(int64_t state, bool startup)
  {
    if (state < 0 || state > 2) {
      RCLCPP_WARN(get_logger(), "Ignoring invalid grasp state %ld; expected 0, 1, or 2", state);
      return;
    }
    const auto message = make_array(positions_[static_cast<std::size_t>(state)]);
    if (left_joint_pub_) left_joint_pub_->publish(message);
    if (right_joint_pub_) right_joint_pub_->publish(message);
    RCLCPP_INFO(get_logger(), "%s grasp state %ld (%s)", startup ? "Initial" : "Set", state,
                state == 0 ? "open" : (state == 1 ? "pregrasp" : "grasp"));
  }

  std::string robot_namespace_, hand_type_, side_;
  std::vector<uint8_t> positions_[3];
  std::map<std::string, std::vector<uint8_t>> gestures_;
  std::vector<uint8_t> speed_values_, force_values_;
  rclcpp::Publisher<Array>::SharedPtr left_joint_pub_, right_joint_pub_;
  rclcpp::Publisher<Array>::SharedPtr left_speed_pub_, right_speed_pub_;
  rclcpp::Publisher<Array>::SharedPtr left_force_pub_, right_force_pub_;
  rclcpp::Subscription<std_msgs::msg::UInt8>::SharedPtr state_sub_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr gesture_sub_;
  rclcpp::TimerBase::SharedPtr startup_timer_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  try {
    rclcpp::spin(std::make_shared<HandGraspNode>());
  } catch (const std::exception &error) {
    std::cerr << "hand_grasp_control: " << error.what() << std::endl;
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::shutdown();
  return 0;
}
