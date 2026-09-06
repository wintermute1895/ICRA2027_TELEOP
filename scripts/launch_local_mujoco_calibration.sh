#!/usr/bin/env bash
# Start the MuJoCo calibration GUI on ilex22's local desktop from SSH.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${MPC_PYTHON:-/home/ilex/miniforge3/envs/mpc_env/bin/python}"
MODEL="$ROOT/assets/robots/linker_platform/sensorized/a7_dual_arm_l10_hands_cameras.mjcf.xml"
CALIBRATION="$ROOT/config/sim/mujoco_sensor_calibration.json"
LOG_FILE="${MUJOCO_CALIBRATION_LOG:-/tmp/mujoco_calibration.log}"

[[ -x "$PYTHON_BIN" ]] || { echo "[FATAL] MuJoCo Python not found: $PYTHON_BIN" >&2; exit 2; }
[[ -f "$MODEL" ]] || { echo "[FATAL] model not found: $MODEL" >&2; exit 2; }

if [[ -z "${DISPLAY:-}" || -z "${XAUTHORITY:-}" ]]; then
  GUI_PID="$(pgrep -u "$USER" -n gnome-shell || true)"
  [[ -n "$GUI_PID" ]] || { echo "[FATAL] no local GNOME session for $USER; log into and unlock ilex22 first" >&2; exit 3; }
  while IFS= read -r entry; do export "$entry"; done < <(tr '\0' '\n' <"/proc/$GUI_PID/environ" | grep -E '^(DISPLAY|XAUTHORITY|XDG_RUNTIME_DIR)=')
fi

[[ -n "${DISPLAY:-}" ]] || { echo "[FATAL] local DISPLAY was not found" >&2; exit 3; }
[[ -n "${XAUTHORITY:-}" && -r "$XAUTHORITY" ]] || { echo "[FATAL] local XAUTHORITY was not found or is unreadable" >&2; exit 3; }

extra=()
[[ -f "$CALIBRATION" ]] && extra+=(--load "$CALIBRATION")
nohup env DISPLAY="$DISPLAY" XAUTHORITY="$XAUTHORITY" MUJOCO_GL=glfw \
  "$PYTHON_BIN" -B "$ROOT/tools/interactive_mujoco_calibration.py" \
  --model "$MODEL" --output "$CALIBRATION" "${extra[@]}" \
  >"$LOG_FILE" 2>&1 </dev/null &

echo "[PASS] local MuJoCo GUI launched (pid=$!)"
echo "[PASS] calibration=$CALIBRATION"
echo "[PASS] log=$LOG_FILE"
