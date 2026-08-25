#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec /usr/bin/python3 ros_hand_gesture_player.py \
  --side right --robot-namespace robot1 --can can0 --direct-can \
  --output gestures --rate 10
