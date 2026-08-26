// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from lbot_arm_interfaces:srv/SetZero.idl
// generated code does not contain a copyright notice

#ifndef LBOT_ARM_INTERFACES__SRV__DETAIL__SET_ZERO__STRUCT_HPP_
#define LBOT_ARM_INTERFACES__SRV__DETAIL__SET_ZERO__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


#ifndef _WIN32
# define DEPRECATED__lbot_arm_interfaces__srv__SetZero_Request __attribute__((deprecated))
#else
# define DEPRECATED__lbot_arm_interfaces__srv__SetZero_Request __declspec(deprecated)
#endif

namespace lbot_arm_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct SetZero_Request_
{
  using Type = SetZero_Request_<ContainerAllocator>;

  explicit SetZero_Request_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->structure_needs_at_least_one_member = 0;
    }
  }

  explicit SetZero_Request_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    (void)_alloc;
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->structure_needs_at_least_one_member = 0;
    }
  }

  // field types and members
  using _structure_needs_at_least_one_member_type =
    uint8_t;
  _structure_needs_at_least_one_member_type structure_needs_at_least_one_member;


  // constant declarations

  // pointer types
  using RawPtr =
    lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator> *;
  using ConstRawPtr =
    const lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__lbot_arm_interfaces__srv__SetZero_Request
    std::shared_ptr<lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__lbot_arm_interfaces__srv__SetZero_Request
    std::shared_ptr<lbot_arm_interfaces::srv::SetZero_Request_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const SetZero_Request_ & other) const
  {
    if (this->structure_needs_at_least_one_member != other.structure_needs_at_least_one_member) {
      return false;
    }
    return true;
  }
  bool operator!=(const SetZero_Request_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct SetZero_Request_

// alias to use template instance with default allocator
using SetZero_Request =
  lbot_arm_interfaces::srv::SetZero_Request_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace lbot_arm_interfaces


#ifndef _WIN32
# define DEPRECATED__lbot_arm_interfaces__srv__SetZero_Response __attribute__((deprecated))
#else
# define DEPRECATED__lbot_arm_interfaces__srv__SetZero_Response __declspec(deprecated)
#endif

namespace lbot_arm_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct SetZero_Response_
{
  using Type = SetZero_Response_<ContainerAllocator>;

  explicit SetZero_Response_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
    }
  }

  explicit SetZero_Response_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    (void)_alloc;
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
    }
  }

  // field types and members
  using _success_type =
    bool;
  _success_type success;

  // setters for named parameter idiom
  Type & set__success(
    const bool & _arg)
  {
    this->success = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator> *;
  using ConstRawPtr =
    const lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__lbot_arm_interfaces__srv__SetZero_Response
    std::shared_ptr<lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__lbot_arm_interfaces__srv__SetZero_Response
    std::shared_ptr<lbot_arm_interfaces::srv::SetZero_Response_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const SetZero_Response_ & other) const
  {
    if (this->success != other.success) {
      return false;
    }
    return true;
  }
  bool operator!=(const SetZero_Response_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct SetZero_Response_

// alias to use template instance with default allocator
using SetZero_Response =
  lbot_arm_interfaces::srv::SetZero_Response_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace lbot_arm_interfaces

namespace lbot_arm_interfaces
{

namespace srv
{

struct SetZero
{
  using Request = lbot_arm_interfaces::srv::SetZero_Request;
  using Response = lbot_arm_interfaces::srv::SetZero_Response;
};

}  // namespace srv

}  // namespace lbot_arm_interfaces

#endif  // LBOT_ARM_INTERFACES__SRV__DETAIL__SET_ZERO__STRUCT_HPP_
