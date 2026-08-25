#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec /usr/bin/python3 -m hand_gesture_recorder.recorder \
  --hand O6 --side right --can can0 --output gestures --step 1 --overwrite "$@"
