// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from lbot_arm_interfaces:srv/GetFrame.idl
// generated code does not contain a copyright notice

#ifndef LBOT_ARM_INTERFACES__SRV__DETAIL__GET_FRAME__STRUCT_HPP_
#define LBOT_ARM_INTERFACES__SRV__DETAIL__GET_FRAME__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


#ifndef _WIN32
# define DEPRECATED__lbot_arm_interfaces__srv__GetFrame_Request __attribute__((deprecated))
#else
# define DEPRECATED__lbot_arm_interfaces__srv__GetFrame_Request __declspec(deprecated)
#endif

namespace lbot_arm_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct GetFrame_Request_
{
  using Type = GetFrame_Request_<ContainerAllocator>;

  explicit GetFrame_Request_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->name = "";
    }
  }

  explicit GetFrame_Request_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : name(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->name = "";
    }
  }

  // field types and members
  using _name_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _name_type name;

  // setters for named parameter idiom
  Type & set__name(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->name = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator> *;
  using ConstRawPtr =
    const lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__lbot_arm_interfaces__srv__GetFrame_Request
    std::shared_ptr<lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__lbot_arm_interfaces__srv__GetFrame_Request
    std::shared_ptr<lbot_arm_interfaces::srv::GetFrame_Request_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const GetFrame_Request_ & other) const
  {
    if (this->name != other.name) {
      return false;
    }
    return true;
  }
  bool operator!=(const GetFrame_Request_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct GetFrame_Request_

// alias to use template instance with default allocator
using GetFrame_Request =
  lbot_arm_interfaces::srv::GetFrame_Request_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace lbot_arm_interfaces


// Include directives for member types
// Member 'frame'
#include "lbot_arm_interfaces/msg/detail/lbot_frame__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__lbot_arm_interfaces__srv__GetFrame_Response __attribute__((deprecated))
#else
# define DEPRECATED__lbot_arm_interfaces__srv__GetFrame_Response __declspec(deprecated)
#endif

namespace lbot_arm_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct GetFrame_Response_
{
  using Type = GetFrame_Response_<ContainerAllocator>;

  explicit GetFrame_Response_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : frame(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
    }
  }

  explicit GetFrame_Response_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : frame(_alloc, _init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
    }
  }

  // field types and members
  using _frame_type =
    lbot_arm_interfaces::msg::LbotFrame_<ContainerAllocator>;
  _frame_type frame;
  using _success_type =
    bool;
  _success_type success;

  // setters for named parameter idiom
  Type & set__frame(
    const lbot_arm_interfaces::msg::LbotFrame_<ContainerAllocator> & _arg)
  {
    this->frame = _arg;
    return *this;
  }
  Type & set__success(
    const bool & _arg)
  {
    this->success = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator> *;
  using ConstRawPtr =
    const lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__lbot_arm_interfaces__srv__GetFrame_Response
    std::shared_ptr<lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__lbot_arm_interfaces__srv__GetFrame_Response
    std::shared_ptr<lbot_arm_interfaces::srv::GetFrame_Response_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const GetFrame_Response_ & other) const
  {
    if (this->frame != other.frame) {
      return false;
    }
    if (this->success != other.success) {
      return false;
    }
    return true;
  }
  bool operator!=(const GetFrame_Response_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct GetFrame_Response_

// alias to use template instance with default allocator
using GetFrame_Response =
  lbot_arm_interfaces::srv::GetFrame_Response_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace lbot_arm_interfaces

namespace lbot_arm_interfaces
{

namespace srv
{

struct GetFrame
{
  using Request = lbot_arm_interfaces::srv::GetFrame_Request;
  using Response = lbot_arm_interfaces::srv::GetFrame_Response;
};

}  // namespace srv

}  // namespace lbot_arm_interfaces

#endif  // LBOT_ARM_INTERFACES__SRV__DETAIL__GET_FRAME__STRUCT_HPP_
