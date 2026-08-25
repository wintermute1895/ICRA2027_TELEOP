#!/bin/bash
# 一键打开 D0 遥操录包的四个 tmux 窗口：
#   camera  / teleop  / hand(O6)  / record
#
# 记录器在 record 窗口里手工执行 scripts/d0_record.py，见 scripts/README.md。
SESSION=d0
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "[tmux] 清理旧节点（避免重复发布者）..."
"$PROJECT_ROOT/scripts/stop_teleop.sh"

if tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux attach -t "$SESSION"
  exit 0
fi

ENV="source $PROJECT_ROOT/scripts/d0_env.sh"

tmux new-session -d -s "$SESSION" -n camera
tmux send-keys -t "$SESSION:camera" "$ENV" C-m
tmux send-keys -t "$SESSION:camera" "ros2 launch realsense2_camera rs_launch.py enable_depth:=true enable_color:=true rgb_camera.color_profile:=640,480,15 depth_module.depth_profile:=640,480,15" C-m

tmux new-window -t "$SESSION" -n teleop
tmux send-keys -t "$SESSION:teleop" "$ENV" C-m
tmux send-keys -t "$SESSION:teleop" "ros2 launch lbot_teleop teleop.launch.py armed:=true" C-m

tmux new-window -t "$SESSION" -n hand
tmux send-keys -t "$SESSION:hand" "$ENV" C-m
tmux send-keys -t "$SESSION:hand" "cd $PROJECT_ROOT/L10_Hand_Gesture_Tool" C-m
tmux send-keys -t "$SESSION:hand" "./run_ros_gui_o6_right.sh" C-m

tmux new-window -t "$SESSION" -n record
tmux send-keys -t "$SESSION:record" "$ENV" C-m
tmux send-keys -t "$SESSION:record" "cd $PROJECT_ROOT" C-m

tmux select-window -t "$SESSION:camera"
tmux attach -t "$SESSION"
