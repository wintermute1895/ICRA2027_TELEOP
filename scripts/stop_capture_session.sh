#!/usr/bin/env bash
set -Eeuo pipefail

SESSION="${1:-teleop_capture}"
if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed" >&2
  exit 2
fi
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Stopping tmux session: $SESSION"
  tmux kill-session -t "$SESSION"
  echo "Session stopped. Existing evidence files were not removed."
else
  echo "No tmux session found: $SESSION"
fi

# tmux does not always propagate signals through ROS launch wrappers.  Ask the
# known capture processes to terminate gracefully, without touching unrelated
# applications.
for pattern in 'ros2 bag record' 'realsense2_camera_node' 'linkerta_node' 'joint_mapping_bridge_node' 'lbot_driver'; do
  pids="$(pgrep -f "$pattern" || true)"
  if [[ -n "$pids" ]]; then
    echo "Stopping residual $pattern: $pids"
    kill -INT $pids 2>/dev/null || true
    for _ in {1..15}; do
      sleep 0.2
      alive="$(pgrep -f "$pattern" || true)"
      [[ -z "$alive" ]] && break
    done
    alive="$(pgrep -f "$pattern" || true)"
    if [[ -n "$alive" ]]; then
      echo "Graceful stop timed out; sending TERM: $alive"
      kill -TERM $alive 2>/dev/null || true
      sleep 1
      alive="$(pgrep -f "$pattern" || true)"
    fi
    if [[ -n "$alive" ]]; then
      echo "TERM timed out; sending KILL: $alive"
      kill -KILL $alive 2>/dev/null || true
    fi
  fi
done
