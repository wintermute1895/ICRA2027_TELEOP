// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from lbot_arm_interfaces:srv/SetZero.idl
// generated code does not contain a copyright notice

#ifndef LBOT_ARM_INTERFACES__SRV__DETAIL__SET_ZERO__TRAITS_HPP_
#define LBOT_ARM_INTERFACES__SRV__DETAIL__SET_ZERO__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "lbot_arm_interfaces/srv/detail/set_zero__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

namespace lbot_arm_interfaces
{

namespace srv
{

inline void to_flow_style_yaml(
  const SetZero_Request & msg,
  std::ostream & out)
{
  (void)msg;
  out << "null";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const SetZero_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  (void)msg;
  (void)indentation;
  out << "null\n";
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const SetZero_Request & msg, bool use_flow_style = false)
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
  const lbot_arm_interfaces::srv::SetZero_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  lbot_arm_interfaces::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use lbot_arm_interfaces::srv::to_yaml() instead")]]
inline std::string to_yaml(const lbot_arm_interfaces::srv::SetZero_Request & msg)
{
  return lbot_arm_interfaces::srv::to_yaml(msg);
}

template<>
inline const char * data_type<lbot_arm_interfaces::srv::SetZero_Request>()
{
  return "lbot_arm_interfaces::srv::SetZero_Request";
}

template<>
inline const char * name<lbot_arm_interfaces::srv::SetZero_Request>()
{
  return "lbot_arm_interfaces/srv/SetZero_Request";
}

template<>
struct has_fixed_size<lbot_arm_interfaces::srv::SetZero_Request>
  : std::integral_constant<bool, true> {};

template<>
struct has_bounded_size<lbot_arm_interfaces::srv::SetZero_Request>
  : std::integral_constant<bool, true> {};

template<>
struct is_message<lbot_arm_interfaces::srv::SetZero_Request>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace lbot_arm_interfaces
{

namespace srv
{

inline void to_flow_style_yaml(
  const SetZero_Response & msg,
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
  const SetZero_Response & msg,
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

inline std::string to_yaml(const SetZero_Response & msg, bool use_flow_style = false)
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
  const lbot_arm_interfaces::srv::SetZero_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  lbot_arm_interfaces::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use lbot_arm_interfaces::srv::to_yaml() instead")]]
inline std::string to_yaml(const lbot_arm_interfaces::srv::SetZero_Response & msg)
{
  return lbot_arm_interfaces::srv::to_yaml(msg);
}

template<>
inline const char * data_type<lbot_arm_interfaces::srv::SetZero_Response>()
{
  return "lbot_arm_interfaces::srv::SetZero_Response";
}

template<>
inline const char * name<lbot_arm_interfaces::srv::SetZero_Response>()
{
  return "lbot_arm_interfaces/srv/SetZero_Response";
}

template<>
struct has_fixed_size<lbot_arm_interfaces::srv::SetZero_Response>
  : std::integral_constant<bool, true> {};

template<>
struct has_bounded_size<lbot_arm_interfaces::srv::SetZero_Response>
  : std::integral_constant<bool, true> {};

template<>
struct is_message<lbot_arm_interfaces::srv::SetZero_Response>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<lbot_arm_interfaces::srv::SetZero>()
{
  return "lbot_arm_interfaces::srv::SetZero";
}

template<>
inline const char * name<lbot_arm_interfaces::srv::SetZero>()
{
  return "lbot_arm_interfaces/srv/SetZero";
}

template<>
struct has_fixed_size<lbot_arm_interfaces::srv::SetZero>
  : std::integral_constant<
    bool,
    has_fixed_size<lbot_arm_interfaces::srv::SetZero_Request>::value &&
    has_fixed_size<lbot_arm_interfaces::srv::SetZero_Response>::value
  >
{
};

template<>
struct has_bounded_size<lbot_arm_interfaces::srv::SetZero>
  : std::integral_constant<
    bool,
    has_bounded_size<lbot_arm_interfaces::srv::SetZero_Request>::value &&
    has_bounded_size<lbot_arm_interfaces::srv::SetZero_Response>::value
  >
{
};

template<>
struct is_service<lbot_arm_interfaces::srv::SetZero>
  : std::true_type
{
};

template<>
struct is_service_request<lbot_arm_interfaces::srv::SetZero_Request>
  : std::true_type
{
};

template<>
struct is_service_response<lbot_arm_interfaces::srv::SetZero_Response>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits

#endif  // LBOT_ARM_INTERFACES__SRV__DETAIL__SET_ZERO__TRAITS_HPP_
