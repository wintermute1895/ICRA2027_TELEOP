#!/usr/bin/env bash
# Open the local MuJoCo scene editor and a live SSH-visible status window.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${MPC_PYTHON:-/home/ilex/miniforge3/envs/mpc_env/bin/python}"
SESSION="${A7_SCENE_EDITOR_SESSION:-a7_scene_editor}"
LOG_FILE="${A7_SCENE_EDITOR_LOG:-/tmp/a7_scene_editor.log}"

[[ -x "$PYTHON_BIN" ]] || { echo "[FATAL] missing MuJoCo Python: $PYTHON_BIN" >&2; exit 2; }
command -v tmux >/dev/null || { echo "[FATAL] tmux is required" >&2; exit 2; }
if [[ -z "${DISPLAY:-}" || -z "${XAUTHORITY:-}" ]]; then
  GUI_PID="$(pgrep -u "$USER" -n gnome-shell || true)"
  [[ -n "$GUI_PID" ]] || { echo "[FATAL] no unlocked local GNOME session" >&2; exit 3; }
  while IFS= read -r entry; do export "$entry"; done < <(tr '\0' '\n' <"/proc/$GUI_PID/environ" | grep -E '^(DISPLAY|XAUTHORITY|XDG_RUNTIME_DIR)=')
fi
[[ -r "${XAUTHORITY:-}" ]] || { echo "[FATAL] XAUTHORITY unavailable" >&2; exit 3; }
tmux has-session -t "$SESSION" 2>/dev/null && { echo "[FATAL] tmux session already exists: $SESSION" >&2; exit 4; }

"$PYTHON_BIN" -B "$ROOT/tools/build_a7_task_scene.py"
tmux new-session -d -s "$SESSION" -n editor "cd '$ROOT' && env DISPLAY='$DISPLAY' XAUTHORITY='$XAUTHORITY' MUJOCO_GL=glfw '$PYTHON_BIN' -B tools/interactive_mujoco_scene_editor.py 2>&1 | tee '$LOG_FILE'; exec bash"
tmux new-window -t "$SESSION" -n status "tail -F '$LOG_FILE'"
echo "[PASS] local editor started; SSH status: tmux attach -t $SESSION"
echo "[PASS] close: tmux kill-session -t $SESSION"
