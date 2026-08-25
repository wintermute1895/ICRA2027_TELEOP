#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec python hand_gesture_player.py --hand L10 --side right --can can0 --output gestures
