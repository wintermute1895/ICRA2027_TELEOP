cmake_minimum_required(VERSION 3.8)
project(lbot_driver)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_compile_options(-Wall -Wextra -Wpedantic)

# ROS2 dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(lbot_arm_interfaces REQUIRED)

# Vendor SDK is a third-party dependency, not part of the ROS2 package source.
set(LINKERBOT_SDK_ROOT "${PROJECT_SOURCE_DIR}/../../../third_party/linkerbot_sdk")
if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
  set(LINKERBOT_SDK_LIB_DIR "${LINKERBOT_SDK_ROOT}/lib/linux_arm64")
else()
  set(LINKERBOT_SDK_LIB_DIR "${LINKERBOT_SDK_ROOT}/lib/linux_x64")
endif()
if(NOT EXISTS "${LINKERBOT_SDK_LIB_DIR}/liblbot_api.so")
  message(FATAL_ERROR "LinkerBot SDK not found at ${LINKERBOT_SDK_LIB_DIR}")
endif()
link_directories("${LINKERBOT_SDK_LIB_DIR}")

# ROS2 driver headers plus official SDK headers.
include_directories(
  ${PROJECT_SOURCE_DIR}/include
  ${PROJECT_SOURCE_DIR}/include/${PROJECT_NAME}
  "${LINKERBOT_SDK_ROOT}/include"
)

# executable
add_executable(lbot_driver src/lbot_driver.cpp)

# link the API library (name only! no lib prefix, no .so suffix)
target_link_libraries(lbot_driver
  lbot_api_cpp
  lbot_api
)

# ros deps
ament_target_dependencies(lbot_driver
  rclcpp
  std_msgs
  std_srvs
  sensor_msgs
  geometry_msgs
  tf2
  tf2_geometry_msgs
  lbot_arm_interfaces
)

# install binary
install(TARGETS lbot_driver
  DESTINATION lib/${PROJECT_NAME}
)

# install launch & config
install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

# install the selected vendor SDK libraries into the package runtime lib path
install(DIRECTORY "${LINKERBOT_SDK_LIB_DIR}/"
  DESTINATION lib
)

ament_package()
