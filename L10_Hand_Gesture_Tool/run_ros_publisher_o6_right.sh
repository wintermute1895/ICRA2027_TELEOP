#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec /usr/bin/python3 ros_hand_publisher.py \
  --hand O6 --side right --robot-namespace robot1 \
  --output gestures --rate 10
