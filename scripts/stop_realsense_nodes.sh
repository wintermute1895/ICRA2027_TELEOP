#!/usr/bin/env bash
# Stop only RealSense ROS camera processes so another client can open the device.
set -euo pipefail

declare -A pids=()
for pattern in 'realsense2_camera_node' 'ros2 launch realsense2_camera'; do
  while IFS= read -r pid; do
    [[ -n "$pid" && "$pid" != "$$" ]] && pids["$pid"]=1
  done < <(pgrep -f "$pattern" || true)
done

if ((${#pids[@]} == 0)); then
  echo 'No RealSense ROS camera processes are running.'
  exit 0
fi

echo "Stopping RealSense ROS camera process(es): ${!pids[*]}"
kill -TERM "${!pids[@]}"

for _ in {1..25}; do
  sleep 0.2
  alive=0
  for pid in "${!pids[@]}"; do
    kill -0 "$pid" 2>/dev/null && alive=1
  done
  (( alive == 0 )) && break
done

remaining=()
for pid in "${!pids[@]}"; do
  kill -0 "$pid" 2>/dev/null && remaining+=("$pid")
done

if ((${#remaining[@]})); then
  printf 'Still running after graceful stop: %s\n' "${remaining[*]}" >&2
  exit 1
fi

echo 'RealSense ROS camera processes stopped. You can now start realsense-viewer.'
