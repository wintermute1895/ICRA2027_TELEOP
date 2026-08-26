// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from lbot_arm_interfaces:srv/MoveJ.idl
// generated code does not contain a copyright notice

#ifndef LBOT_ARM_INTERFACES__SRV__DETAIL__MOVE_J__TRAITS_HPP_
#define LBOT_ARM_INTERFACES__SRV__DETAIL__MOVE_J__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "lbot_arm_interfaces/srv/detail/move_j__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

namespace lbot_arm_interfaces
{

namespace srv
{

inline void to_flow_style_yaml(
  const MoveJ_Request & msg,
  std::ostream & out)
{
  out << "{";
  // member: joints
  {
    if (msg.joints.size() == 0) {
      out << "joints: []";
    } else {
      out << "joints: [";
      size_t pending_items = msg.joints.size();
      for (auto item : msg.joints) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: speed
  {
    out << "speed: ";
    rosidl_generator_traits::value_to_yaml(msg.speed, out);
    out << ", ";
  }

  // member: acce
  {
    out << "acce: ";
    rosidl_generator_traits::value_to_yaml(msg.acce, out);
    out << ", ";
  }

  // member: block
  {
    out << "block: ";
    rosidl_generator_traits::value_to_yaml(msg.block, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const MoveJ_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: joints
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.joints.size() == 0) {
      out << "joints: []\n";
    } else {
      out << "joints:\n";
      for (auto item : msg.joints) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: speed
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "speed: ";
    rosidl_generator_traits::value_to_yaml(msg.speed, out);
    out << "\n";
  }

  // member: acce
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "acce: ";
    rosidl_generator_traits::value_to_yaml(msg.acce, out);
    out << "\n";
  }

  // member: block
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "block: ";
    rosidl_generator_traits::value_to_yaml(msg.block, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const MoveJ_Request & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace srv

}  // namespace lbot_arm_interfaces

namespace rosidl_generator_traits
{

[[deprecated("use lbot_arm_interfaces::srv::to_block_style_yaml() instead")]]
inline void to_yaml(
  const lbot_arm_interfaces::srv::MoveJ_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  lbot_arm_interfaces::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use lbot_arm_interfaces::srv::to_yaml() instead")]]
inline std::string to_yaml(const lbot_arm_interfaces::srv::MoveJ_Request & msg)
{
  return lbot_arm_interfaces::srv::to_yaml(msg);
}

template<>
inline const char * data_type<lbot_arm_interfaces::srv::MoveJ_Request>()
{
  return "lbot_arm_interfaces::srv::MoveJ_Request";
}

template<>
inline const char * name<lbot_arm_interfaces::srv::MoveJ_Request>()
{
  return "lbot_arm_interfaces/srv/MoveJ_Request";
}

template<>
struct has_fixed_size<lbot_arm_interfaces::srv::MoveJ_Request>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<lbot_arm_interfaces::srv::MoveJ_Request>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<lbot_arm_interfaces::srv::MoveJ_Request>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace lbot_arm_interfaces
{

namespace srv
{

inline void to_flow_style_yaml(
  const MoveJ_Response & msg,
  std::ostream & out)
{
  out << "{";
  // member: success
  {
    out << "success: ";
    rosidl_generator_traits::value_to_yaml(msg.success, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const MoveJ_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: success
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "success: ";
    rosidl_generator_traits::value_to_yaml(msg.success, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const MoveJ_Response & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace srv

}  // namespace lbot_arm_interfaces

namespace rosidl_generator_traits
{

[[deprecated("use lbot_arm_interfaces::srv::to_block_style_yaml() instead")]]
inline void to_yaml(
  const lbot_arm_interfaces::srv::MoveJ_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  lbot_arm_interfaces::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use lbot_arm_interfaces::srv::to_yaml() instead")]]
inline std::string to_yaml(const lbot_arm_interfaces::srv::MoveJ_Response & msg)
{
  return lbot_arm_interfaces::srv::to_yaml(msg);
}

template<>
inline const char * data_type<lbot_arm_interfaces::srv::MoveJ_Response>()
{
  return "lbot_arm_interfaces::srv::MoveJ_Response";
}

template<>
inline const char * name<lbot_arm_interfaces::srv::MoveJ_Response>()
{
  return "lbot_arm_interfaces/srv/MoveJ_Response";
}

template<>
struct has_fixed_size<lbot_arm_interfaces::srv::MoveJ_Response>
  : std::integral_constant<bool, true> {};

template<>
struct has_bounded_size<lbot_arm_interfaces::srv::MoveJ_Response>
  : std::integral_constant<bool, true> {};

template<>
struct is_message<lbot_arm_interfaces::srv::MoveJ_Response>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<lbot_arm_interfaces::srv::MoveJ>()
{
  return "lbot_arm_interfaces::srv::MoveJ";
}

template<>
inline const char * name<lbot_arm_interfaces::srv::MoveJ>()
{
  return "lbot_arm_interfaces/srv/MoveJ";
}

template<>
struct has_fixed_size<lbot_arm_interfaces::srv::MoveJ>
  : std::integral_constant<
    bool,
    has_fixed_size<lbot_arm_interfaces::srv::MoveJ_Request>::value &&
    has_fixed_size<lbot_arm_interfaces::srv::MoveJ_Response>::value
  >
{
};

template<>
struct has_bounded_size<lbot_arm_interfaces::srv::MoveJ>
  : std::integral_constant<
    bool,
    has_bounded_size<lbot_arm_interfaces::srv::MoveJ_Request>::value &&
    has_bounded_size<lbot_arm_interfaces::srv::MoveJ_Response>::value
  >
{
};

template<>
struct is_service<lbot_arm_interfaces::srv::MoveJ>
  : std::true_type
{
};

template<>
struct is_service_request<lbot_arm_interfaces::srv::MoveJ_Request>
  : std::true_type
{
};

template<>
struct is_service_response<lbot_arm_interfaces::srv::MoveJ_Response>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits

#endif  // LBOT_ARM_INTERFACES__SRV__DETAIL__MOVE_J__TRAITS_HPP_
