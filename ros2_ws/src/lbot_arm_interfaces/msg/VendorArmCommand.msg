# A command accepted by the ROS2 hardware driver immediately before it calls
# the official LinkerBot SDK.  All joint values are radians in vendor order.

uint8 MODE_FOLLOW=0
uint8 MODE_MOVEJ=1

std_msgs/Header header
uint8 mode
string arm
float64[] joints_rad
float64 speed_rad_s
float64 accel_rad_s2
bool block
bool follow
string source
