#!/usr/bin/env bash
set -Eeuo pipefail

SESSION="${1:-teleop_capture}"
if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed" >&2
  exit 2
fi
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "No tmux session found: $SESSION"
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
