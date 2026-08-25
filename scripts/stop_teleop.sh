#!/bin/bash
# 清理遥操录制相关进程，避免旧节点残留导致预检出现重复发布者
# （/vist/*、/robot1/*_arm/* 等话题 Publisher count = 2）。
# 与 遥操.odt 顶部的清理逻辑一致。
tmux kill-server 2>/dev/null || true
pkill -9 -f 'lbot_driver' 2>/dev/null || true
pkill -9 -f 'linkerta' 2>/dev/null || true
pkill -9 -f 'teleop_bridge_node' 2>/dev/null || true
pkill -9 -f 'hand_gesture_player.py' 2>/dev/null || true
pkill -9 -f 'ros_hand_publisher.py' 2>/dev/null || true
pkill -9 -f 'ros_hand_gesture_player.py' 2>/dev/null || true
pkill -9 -f 'image_transport republish' 2>/dev/null || true
pkill -9 -f 'ros2 launch' 2>/dev/null || true
echo "[stop] teleop/record 相关进程已清理"
