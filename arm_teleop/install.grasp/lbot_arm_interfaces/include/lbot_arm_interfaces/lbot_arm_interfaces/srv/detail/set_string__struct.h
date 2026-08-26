// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from lbot_arm_interfaces:srv/SetString.idl
// generated code does not contain a copyright notice

#ifndef LBOT_ARM_INTERFACES__SRV__DETAIL__SET_STRING__STRUCT_H_
#define LBOT_ARM_INTERFACES__SRV__DETAIL__SET_STRING__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'name'
#include "rosidl_runtime_c/string.h"

/// Struct defined in srv/SetString in the package lbot_arm_interfaces.
typedef struct lbot_arm_interfaces__srv__SetString_Request
{
  rosidl_runtime_c__String name;
} lbot_arm_interfaces__srv__SetString_Request;

// Struct for a sequence of lbot_arm_interfaces__srv__SetString_Request.
typedef struct lbot_arm_interfaces__srv__SetString_Request__Sequence
{
  lbot_arm_interfaces__srv__SetString_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} lbot_arm_interfaces__srv__SetString_Request__Sequence;


// Constants defined in the message

/// Struct defined in srv/SetString in the package lbot_arm_interfaces.
typedef struct lbot_arm_interfaces__srv__SetString_Response
{
  bool success;
} lbot_arm_interfaces__srv__SetString_Response;

// Struct for a sequence of lbot_arm_interfaces__srv__SetString_Response.
typedef struct lbot_arm_interfaces__srv__SetString_Response__Sequence
{
  lbot_arm_interfaces__srv__SetString_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} lbot_arm_interfaces__srv__SetString_Response__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // LBOT_ARM_INTERFACES__SRV__DETAIL__SET_STRING__STRUCT_H_
