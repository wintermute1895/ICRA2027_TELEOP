// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from lbot_arm_interfaces:srv/GetAllFrames.idl
// generated code does not contain a copyright notice

#ifndef LBOT_ARM_INTERFACES__SRV__DETAIL__GET_ALL_FRAMES__STRUCT_HPP_
#define LBOT_ARM_INTERFACES__SRV__DETAIL__GET_ALL_FRAMES__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


#ifndef _WIN32
# define DEPRECATED__lbot_arm_interfaces__srv__GetAllFrames_Request __attribute__((deprecated))
#else
# define DEPRECATED__lbot_arm_interfaces__srv__GetAllFrames_Request __declspec(deprecated)
#endif

namespace lbot_arm_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct GetAllFrames_Request_
{
  using Type = GetAllFrames_Request_<ContainerAllocator>;

  explicit GetAllFrames_Request_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->structure_needs_at_least_one_member = 0;
    }
  }

  explicit GetAllFrames_Request_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
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
    lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator> *;
  using ConstRawPtr =
    const lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__lbot_arm_interfaces__srv__GetAllFrames_Request
    std::shared_ptr<lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__lbot_arm_interfaces__srv__GetAllFrames_Request
    std::shared_ptr<lbot_arm_interfaces::srv::GetAllFrames_Request_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const GetAllFrames_Request_ & other) const
  {
    if (this->structure_needs_at_least_one_member != other.structure_needs_at_least_one_member) {
      return false;
    }
    return true;
  }
  bool operator!=(const GetAllFrames_Request_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct GetAllFrames_Request_

// alias to use template instance with default allocator
using GetAllFrames_Request =
  lbot_arm_interfaces::srv::GetAllFrames_Request_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace lbot_arm_interfaces


#ifndef _WIN32
# define DEPRECATED__lbot_arm_interfaces__srv__GetAllFrames_Response __attribute__((deprecated))
#else
# define DEPRECATED__lbot_arm_interfaces__srv__GetAllFrames_Response __declspec(deprecated)
#endif

namespace lbot_arm_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct GetAllFrames_Response_
{
  using Type = GetAllFrames_Response_<ContainerAllocator>;

  explicit GetAllFrames_Response_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
    }
  }

  explicit GetAllFrames_Response_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    (void)_alloc;
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
    }
  }

  // field types and members
  using _names_type =
    std::vector<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>>>;
  _names_type names;
  using _success_type =
    bool;
  _success_type success;

  // setters for named parameter idiom
  Type & set__names(
    const std::vector<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>>> & _arg)
  {
    this->names = _arg;
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
    lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator> *;
  using ConstRawPtr =
    const lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__lbot_arm_interfaces__srv__GetAllFrames_Response
    std::shared_ptr<lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__lbot_arm_interfaces__srv__GetAllFrames_Response
    std::shared_ptr<lbot_arm_interfaces::srv::GetAllFrames_Response_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const GetAllFrames_Response_ & other) const
  {
    if (this->names != other.names) {
      return false;
    }
    if (this->success != other.success) {
      return false;
    }
    return true;
  }
  bool operator!=(const GetAllFrames_Response_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct GetAllFrames_Response_

// alias to use template instance with default allocator
using GetAllFrames_Response =
  lbot_arm_interfaces::srv::GetAllFrames_Response_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace lbot_arm_interfaces

namespace lbot_arm_interfaces
{

namespace srv
{

struct GetAllFrames
{
  using Request = lbot_arm_interfaces::srv::GetAllFrames_Request;
  using Response = lbot_arm_interfaces::srv::GetAllFrames_Response;
};

}  // namespace srv

}  // namespace lbot_arm_interfaces

#endif  // LBOT_ARM_INTERFACES__SRV__DETAIL__GET_ALL_FRAMES__STRUCT_HPP_
