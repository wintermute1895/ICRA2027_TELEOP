# LinkerBot SDK vendor bundle

这里集中存放官方 LinkerBot SDK 1.0.3 的二进制库和仅用于诊断的 Python ABI wrapper。

```text
third_party/linkerbot_sdk/
├── include/             官方 C/C++ SDK 头文件
├── lib/linux_x64/       x86_64 动态库
├── lib/linux_arm64/     ARM64 动态库
└── python/              本项目的 ctypes 诊断 wrapper
```

ROS2 驱动源码位于 `ros2_ws/src/lbot_driver`，通过其 CMake 文件选择当前机器架构的
SDK 库。SDK 本身不是 ROS2 package，不要把新的 SDK 文件复制回 ROS2 驱动目录。

`include/lbot_api.h` + `lib/liblbot_api.so` 是官方 C API；
`include/lbot_api_cpp.h` + `lib/liblbot_api_cpp.so` 是官方 C++ 封装。

`python/lbot_sdk_v103.py` 不是独立的官方 Python SDK 包，而是本项目为方向检查编写的
Python `ctypes` wrapper，直接加载官方 C 动态库。它仅供诊断使用，不是实时遥操后端。
实时控制统一经过 ROS2 C++ driver。
