// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from lbot_arm_interfaces:srv/DeleteFrame.idl
// generated code does not contain a copyright notice

#ifndef LBOT_ARM_INTERFACES__SRV__DETAIL__DELETE_FRAME__TRAITS_HPP_
#define LBOT_ARM_INTERFACES__SRV__DETAIL__DELETE_FRAME__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "lbot_arm_interfaces/srv/detail/delete_frame__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

namespace lbot_arm_interfaces
{

namespace srv
{

inline void to_flow_style_yaml(
  const DeleteFrame_Request & msg,
  std::ostream & out)
{
  out << "{";
  // member: name
  {
    out << "name: ";
    rosidl_generator_traits::value_to_yaml(msg.name, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const DeleteFrame_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: name
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "name: ";
    rosidl_generator_traits::value_to_yaml(msg.name, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const DeleteFrame_Request & msg, bool use_flow_style = false)
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
  const lbot_arm_interfaces::srv::DeleteFrame_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  lbot_arm_interfaces::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use lbot_arm_interfaces::srv::to_yaml() instead")]]
inline std::string to_yaml(const lbot_arm_interfaces::srv::DeleteFrame_Request & msg)
{
  return lbot_arm_interfaces::srv::to_yaml(msg);
}

template<>
inline const char * data_type<lbot_arm_interfaces::srv::DeleteFrame_Request>()
{
  return "lbot_arm_interfaces::srv::DeleteFrame_Request";
}

template<>
inline const char * name<lbot_arm_interfaces::srv::DeleteFrame_Request>()
{
  return "lbot_arm_interfaces/srv/DeleteFrame_Request";
}

template<>
struct has_fixed_size<lbot_arm_interfaces::srv::DeleteFrame_Request>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<lbot_arm_interfaces::srv::DeleteFrame_Request>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<lbot_arm_interfaces::srv::DeleteFrame_Request>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace lbot_arm_interfaces
{

namespace srv
{

inline void to_flow_style_yaml(
  const DeleteFrame_Response & msg,
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
  const DeleteFrame_Response & msg,
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

inline std::string to_yaml(const DeleteFrame_Response & msg, bool use_flow_style = false)
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
  const lbot_arm_interfaces::srv::DeleteFrame_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  lbot_arm_interfaces::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use lbot_arm_interfaces::srv::to_yaml() instead")]]
inline std::string to_yaml(const lbot_arm_interfaces::srv::DeleteFrame_Response & msg)
{
  return lbot_arm_interfaces::srv::to_yaml(msg);
}

template<>
inline const char * data_type<lbot_arm_interfaces::srv::DeleteFrame_Response>()
{
  return "lbot_arm_interfaces::srv::DeleteFrame_Response";
}

template<>
inline const char * name<lbot_arm_interfaces::srv::DeleteFrame_Response>()
{
  return "lbot_arm_interfaces/srv/DeleteFrame_Response";
}

template<>
struct has_fixed_size<lbot_arm_interfaces::srv::DeleteFrame_Response>
  : std::integral_constant<bool, true> {};

template<>
struct has_bounded_size<lbot_arm_interfaces::srv::DeleteFrame_Response>
  : std::integral_constant<bool, true> {};

template<>
struct is_message<lbot_arm_interfaces::srv::DeleteFrame_Response>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<lbot_arm_interfaces::srv::DeleteFrame>()
{
  return "lbot_arm_interfaces::srv::DeleteFrame";
}

template<>
inline const char * name<lbot_arm_interfaces::srv::DeleteFrame>()
{
  return "lbot_arm_interfaces/srv/DeleteFrame";
}

template<>
struct has_fixed_size<lbot_arm_interfaces::srv::DeleteFrame>
  : std::integral_constant<
    bool,
    has_fixed_size<lbot_arm_interfaces::srv::DeleteFrame_Request>::value &&
    has_fixed_size<lbot_arm_interfaces::srv::DeleteFrame_Response>::value
  >
{
};

template<>
struct has_bounded_size<lbot_arm_interfaces::srv::DeleteFrame>
  : std::integral_constant<
    bool,
    has_bounded_size<lbot_arm_interfaces::srv::DeleteFrame_Request>::value &&
    has_bounded_size<lbot_arm_interfaces::srv::DeleteFrame_Response>::value
  >
{
};

template<>
struct is_service<lbot_arm_interfaces::srv::DeleteFrame>
  : std::true_type
{
};

template<>
struct is_service_request<lbot_arm_interfaces::srv::DeleteFrame_Request>
  : std::true_type
{
};

template<>
struct is_service_response<lbot_arm_interfaces::srv::DeleteFrame_Response>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits

#endif  // LBOT_ARM_INTERFACES__SRV__DETAIL__DELETE_FRAME__TRAITS_HPP_
