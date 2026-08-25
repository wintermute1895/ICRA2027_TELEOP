#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec /usr/bin/python3 hand_gesture_player.py \
  --hand O6 --side right --can can0 --output gestures \
  --ros-mirror --ros-topic /robot1/right_hand/set_l6_joint --ros-rate 10
