// generated from rosidl_typesupport_introspection_c/resource/idl__type_support.c.em
// with input from lbot_arm_interfaces:srv/GetAllFrames.idl
// generated code does not contain a copyright notice

#include <stddef.h>
#include "lbot_arm_interfaces/srv/detail/get_all_frames__rosidl_typesupport_introspection_c.h"
#include "lbot_arm_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
#include "rosidl_typesupport_introspection_c/field_types.h"
#include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/message_introspection.h"
#include "lbot_arm_interfaces/srv/detail/get_all_frames__functions.h"
#include "lbot_arm_interfaces/srv/detail/get_all_frames__struct.h"


#ifdef __cplusplus
extern "C"
{
#endif

void lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  lbot_arm_interfaces__srv__GetAllFrames_Request__init(message_memory);
}

void lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_fini_function(void * message_memory)
{
  lbot_arm_interfaces__srv__GetAllFrames_Request__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_message_member_array[1] = {
  {
    "structure_needs_at_least_one_member",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_UINT8,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(lbot_arm_interfaces__srv__GetAllFrames_Request, structure_needs_at_least_one_member),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_message_members = {
  "lbot_arm_interfaces__srv",  // message namespace
  "GetAllFrames_Request",  // message name
  1,  // number of fields
  sizeof(lbot_arm_interfaces__srv__GetAllFrames_Request),
  lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_message_member_array,  // message members
  lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_init_function,  // function to initialize message memory (memory has to be allocated)
  lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_message_type_support_handle = {
  0,
  &lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_lbot_arm_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, lbot_arm_interfaces, srv, GetAllFrames_Request)() {
  if (!lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_message_type_support_handle.typesupport_identifier) {
    lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &lbot_arm_interfaces__srv__GetAllFrames_Request__rosidl_typesupport_introspection_c__GetAllFrames_Request_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

// already included above
// #include <stddef.h>
// already included above
// #include "lbot_arm_interfaces/srv/detail/get_all_frames__rosidl_typesupport_introspection_c.h"
// already included above
// #include "lbot_arm_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "rosidl_typesupport_introspection_c/field_types.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
// already included above
// #include "rosidl_typesupport_introspection_c/message_introspection.h"
// already included above
// #include "lbot_arm_interfaces/srv/detail/get_all_frames__functions.h"
// already included above
// #include "lbot_arm_interfaces/srv/detail/get_all_frames__struct.h"


// Include directives for member types
// Member `names`
#include "rosidl_runtime_c/string_functions.h"

#ifdef __cplusplus
extern "C"
{
#endif

void lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  lbot_arm_interfaces__srv__GetAllFrames_Response__init(message_memory);
}

void lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_fini_function(void * message_memory)
{
  lbot_arm_interfaces__srv__GetAllFrames_Response__fini(message_memory);
}

size_t lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__size_function__GetAllFrames_Response__names(
  const void * untyped_member)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return member->size;
}

const void * lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__get_const_function__GetAllFrames_Response__names(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__String__Sequence * member =
    (const rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void * lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__get_function__GetAllFrames_Response__names(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  return &member->data[index];
}

void lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__fetch_function__GetAllFrames_Response__names(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const rosidl_runtime_c__String * item =
    ((const rosidl_runtime_c__String *)
    lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__get_const_function__GetAllFrames_Response__names(untyped_member, index));
  rosidl_runtime_c__String * value =
    (rosidl_runtime_c__String *)(untyped_value);
  *value = *item;
}

void lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__assign_function__GetAllFrames_Response__names(
  void * untyped_member, size_t index, const void * untyped_value)
{
  rosidl_runtime_c__String * item =
    ((rosidl_runtime_c__String *)
    lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__get_function__GetAllFrames_Response__names(untyped_member, index));
  const rosidl_runtime_c__String * value =
    (const rosidl_runtime_c__String *)(untyped_value);
  *item = *value;
}

bool lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__resize_function__GetAllFrames_Response__names(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__String__Sequence * member =
    (rosidl_runtime_c__String__Sequence *)(untyped_member);
  rosidl_runtime_c__String__Sequence__fini(member);
  return rosidl_runtime_c__String__Sequence__init(member, size);
}

static rosidl_typesupport_introspection_c__MessageMember lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_message_member_array[2] = {
  {
    "names",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(lbot_arm_interfaces__srv__GetAllFrames_Response, names),  // bytes offset in struct
    NULL,  // default value
    lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__size_function__GetAllFrames_Response__names,  // size() function pointer
    lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__get_const_function__GetAllFrames_Response__names,  // get_const(index) function pointer
    lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__get_function__GetAllFrames_Response__names,  // get(index) function pointer
    lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__fetch_function__GetAllFrames_Response__names,  // fetch(index, &value) function pointer
    lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__assign_function__GetAllFrames_Response__names,  // assign(index, value) function pointer
    lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__resize_function__GetAllFrames_Response__names  // resize(index) function pointer
  },
  {
    "success",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(lbot_arm_interfaces__srv__GetAllFrames_Response, success),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_message_members = {
  "lbot_arm_interfaces__srv",  // message namespace
  "GetAllFrames_Response",  // message name
  2,  // number of fields
  sizeof(lbot_arm_interfaces__srv__GetAllFrames_Response),
  lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_message_member_array,  // message members
  lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_init_function,  // function to initialize message memory (memory has to be allocated)
  lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_message_type_support_handle = {
  0,
  &lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_lbot_arm_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, lbot_arm_interfaces, srv, GetAllFrames_Response)() {
  if (!lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_message_type_support_handle.typesupport_identifier) {
    lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &lbot_arm_interfaces__srv__GetAllFrames_Response__rosidl_typesupport_introspection_c__GetAllFrames_Response_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

#include "rosidl_runtime_c/service_type_support_struct.h"
// already included above
// #include "lbot_arm_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "lbot_arm_interfaces/srv/detail/get_all_frames__rosidl_typesupport_introspection_c.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/service_introspection.h"

// this is intentionally not const to allow initialization later to prevent an initialization race
static rosidl_typesupport_introspection_c__ServiceMembers lbot_arm_interfaces__srv__detail__get_all_frames__rosidl_typesupport_introspection_c__GetAllFrames_service_members = {
  "lbot_arm_interfaces__srv",  // service namespace
  "GetAllFrames",  // service name
  // these two fields are initialized below on the first access
  NULL,  // request message
  // lbot_arm_interfaces__srv__detail__get_all_frames__rosidl_typesupport_introspection_c__GetAllFrames_Request_message_type_support_handle,
  NULL  // response message
  // lbot_arm_interfaces__srv__detail__get_all_frames__rosidl_typesupport_introspection_c__GetAllFrames_Response_message_type_support_handle
};

static rosidl_service_type_support_t lbot_arm_interfaces__srv__detail__get_all_frames__rosidl_typesupport_introspection_c__GetAllFrames_service_type_support_handle = {
  0,
  &lbot_arm_interfaces__srv__detail__get_all_frames__rosidl_typesupport_introspection_c__GetAllFrames_service_members,
  get_service_typesupport_handle_function,
};

// Forward declaration of request/response type support functions
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, lbot_arm_interfaces, srv, GetAllFrames_Request)();

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, lbot_arm_interfaces, srv, GetAllFrames_Response)();

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_lbot_arm_interfaces
const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_introspection_c, lbot_arm_interfaces, srv, GetAllFrames)() {
  if (!lbot_arm_interfaces__srv__detail__get_all_frames__rosidl_typesupport_introspection_c__GetAllFrames_service_type_support_handle.typesupport_identifier) {
    lbot_arm_interfaces__srv__detail__get_all_frames__rosidl_typesupport_introspection_c__GetAllFrames_service_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  rosidl_typesupport_introspection_c__ServiceMembers * service_members =
    (rosidl_typesupport_introspection_c__ServiceMembers *)lbot_arm_interfaces__srv__detail__get_all_frames__rosidl_typesupport_introspection_c__GetAllFrames_service_type_support_handle.data;

  if (!service_members->request_members_) {
    service_members->request_members_ =
      (const rosidl_typesupport_introspection_c__MessageMembers *)
      ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, lbot_arm_interfaces, srv, GetAllFrames_Request)()->data;
  }
  if (!service_members->response_members_) {
    service_members->response_members_ =
      (const rosidl_typesupport_introspection_c__MessageMembers *)
      ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, lbot_arm_interfaces, srv, GetAllFrames_Response)()->data;
  }

  return &lbot_arm_interfaces__srv__detail__get_all_frames__rosidl_typesupport_introspection_c__GetAllFrames_service_type_support_handle;
}
