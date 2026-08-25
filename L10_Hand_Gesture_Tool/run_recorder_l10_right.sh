#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec python -m hand_gesture_recorder.recorder --hand L10 --side right --can can0 --output gestures --step 1
