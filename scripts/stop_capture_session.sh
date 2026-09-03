#!/usr/bin/env bash
# Safely stop either a tmux-managed capture session or the new Python/Tk
# capture manager.  Never removes evidence files and never powers off robots.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="${1:-teleop_capture}"

# Pin the tmux binary so a conda tmux server and a system tmux client cannot
# disagree.  The Python manager mode does not use tmux at all.
TMUX_SERVER_NAME="${TELEOP_TMUX_SERVER_NAME:-teleop_capture_socket}"
TMUX_BIN="${TELEOP_TMUX_BIN:-}"
if [[ -z "$TMUX_BIN" && -x /usr/bin/tmux ]]; then
  TMUX_BIN="/usr/bin/tmux"
elif [[ -z "$TMUX_BIN" ]]; then
  TMUX_BIN="$(command -v tmux || true)"
fi
tmux() { "$TMUX_BIN" -L "$TMUX_SERVER_NAME" "$@"; }

stop_component_pids() {
  # $1 = JSON state file; $2 = optional label.  Kill manager-owned processes in
  # graceful order using PIDs recorded by the supervisor, then fall back to
  # INT/TERM/KILL for survivors.
  local state_file="$1" label="${2:-component}"
  [[ -f "$state_file" ]] || return 0
  local manager_pid components pids pid
  manager_pid="$(sed -n 's/.*"manager_pid": *\([0-9][0-9]*\).*/\1/p' "$state_file" | head -n 1 || true)"
  if [[ -n "$manager_pid" ]] && kill -0 "$manager_pid" 2>/dev/null; then
    echo "Sending SIGINT to Python manager pid $manager_pid"
    kill -INT "$manager_pid" 2>/dev/null || true
    for _ in {1..50}; do
      kill -0 "$manager_pid" 2>/dev/null || break
      sleep 0.2
    done
    if kill -0 "$manager_pid" 2>/dev/null; then
      echo "Manager did not exit after SIGINT; sending SIGTERM to $manager_pid" >&2
      kill -TERM "$manager_pid" 2>/dev/null || true
      sleep 1
    fi
    if kill -0 "$manager_pid" 2>/dev/null; then
      echo "Manager still alive; sending SIGKILL to $manager_pid" >&2
      kill -KILL "$manager_pid" 2>/dev/null || true
    fi
  fi

  # If the manager is gone, clean up any component process groups it recorded.
  if command -v python3 >/dev/null 2>&1; then
    components="$(python3 - "$state_file" <<'PY' || true
import json, sys
try:
    payload = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    raise SystemExit(0)
pids = []
for value in payload.get("components", {}).values():
    pid = value.get("pid")
    if pid:
        pids.append(str(pid))
recorder_pid = payload.get("recorder_pid")
if recorder_pid:
    pids.append(str(recorder_pid))
print("\n".join(pids))
PY
)"
    for pid in $components; do
      [[ "$pid" =~ ^[0-9]+$ ]] || continue
      kill -0 "$pid" 2>/dev/null || continue
      echo "Stopping leftover $label pid $pid"
      kill -INT "$pid" 2>/dev/null || true
    done
    sleep 1
    for pid in $components; do
      kill -0 "$pid" 2>/dev/null || continue
      kill -TERM "$pid" 2>/dev/null || true
    done
    sleep 1
    for pid in $components; do
      kill -0 "$pid" 2>/dev/null || continue
      kill -KILL "$pid" 2>/dev/null || true
    done
  fi
}

# --- Python / Tk manager mode ---
MARKER="/tmp/teleop_capture_supervisor_${SESSION}-$(id -u).json"
if [[ -f "$MARKER" ]]; then
  echo "Found Python capture manager for session: $SESSION"
  STATE_FILE="$(sed -n 's/.*"state_path": *"\([^"]*\)".*/\1/p' "$MARKER" | head -n 1 || true)"
  if [[ -n "$STATE_FILE" && -f "$STATE_FILE" ]]; then
    stop_component_pids "$STATE_FILE" "supervisor process"
    echo "Session stopped. Existing evidence files were not removed."
    exit 0
  fi
  echo "Marker exists but session state is missing: $MARKER" >&2
  echo "Inspect leftovers manually before retrying." >&2
  exit 2
fi

# --- tmux mode ---
if [[ -z "$TMUX_BIN" || ! -x "$TMUX_BIN" ]]; then
  echo "tmux is not installed and no Python capture manager marker was found" >&2
  exit 2
fi
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "No tmux session or Python capture manager found: $SESSION"
  echo "No processes were killed; inspect leftovers manually before retrying." >&2
  exit 0
fi

echo "Stopping tmux session: $SESSION"

# Capture pane process trees before killing tmux. ROS launch wrappers may
# survive the pane shell, but every process started by this launcher remains a
# descendant of one of these pane PIDs. Never use global pgrep patterns here:
# another user's camera/viewer process must not be touched.
declare -A PIDS=()
collect_descendants() {
  local parent="$1" child
  [[ -n "$parent" ]] || return
  PIDS["$parent"]=1
  while IFS= read -r child; do
    [[ -n "$child" ]] || continue
    [[ -n "${PIDS[$child]+x}" ]] && continue
    collect_descendants "$child"
  done < <(pgrep -P "$parent" 2>/dev/null || true)
}
while IFS= read -r pane_pid; do
  collect_descendants "$pane_pid"
done < <(tmux list-panes -s -t "$SESSION" -F '#{pane_pid}' 2>/dev/null || true)

tmux kill-session -t "$SESSION"
for pid in "${!PIDS[@]}"; do kill -INT "$pid" 2>/dev/null || true; done
for _ in {1..25}; do
  alive=0
  for pid in "${!PIDS[@]}"; do
    kill -0 "$pid" 2>/dev/null && alive=1
  done
  (( alive == 0 )) && break
  sleep 0.2
done
remaining=()
for pid in "${!PIDS[@]}"; do
  kill -0 "$pid" 2>/dev/null && remaining+=("$pid")
done
if ((${#remaining[@]})); then
  echo "Graceful stop timed out; sending TERM to session descendants: ${remaining[*]}" >&2
  for pid in "${remaining[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
  sleep 1
  remaining_after_term=()
  for pid in "${remaining[@]}"; do
    kill -0 "$pid" 2>/dev/null && remaining_after_term+=("$pid")
  done
  if ((${#remaining_after_term[@]})); then
    echo "TERM timed out; sending KILL to session descendants: ${remaining_after_term[*]}" >&2
    for pid in "${remaining_after_term[@]}"; do kill -KILL "$pid" 2>/dev/null || true; done
  fi
fi
echo "Session stopped. Existing evidence files were not removed."
