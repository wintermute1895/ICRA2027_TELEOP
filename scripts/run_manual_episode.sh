#!/usr/bin/env bash
set -Eeuo pipefail

# Interactive parent for manual capture.  It owns the TTY; runevidence and
# record_episode run with detached stdin and are controlled by a stop file.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNEVIDENCE_BIN="${RUNEVIDENCE_BIN:?RUNEVIDENCE_BIN is required}"
RECORDER="${ROOT_DIR}/scripts/record_episode.sh"
RUN_ROOT="${RUNEVIDENCE_ROOT:?RUNEVIDENCE_ROOT is required}"
EPISODES="${TELEOP_CAPTURE_EPISODES:-1}"
EXPERIMENT_ID="${TELEOP_EXPERIMENT_ID:-unassigned}"
CONDITION_ID="${TELEOP_CONDITION_ID:-unassigned}"
OPERATOR_ID="${TELEOP_OPERATOR_ID:-anonymous}"
TASK_ID="${TELEOP_TASK_ID:-unspecified}"

finalize_audit() {
  local run_dir="$1" audit_path="$run_dir/artifacts/terminal_audit.json" outcome reason safety override
  echo
  echo "[AUDIT] 数据已保存。审计填写可选；直接回车将标记为 audit_deferred。"
  read -r -p "现在填写本条审计？[Y/n]: " audit_now
  if [[ "${audit_now,,}" == n || "${audit_now,,}" == no ]]; then
    /usr/bin/python3 "$ROOT_DIR/tools/finalize_episode_audit.py" --output "$audit_path" \
      --episode-id "$(basename "$run_dir")" --failure --termination-reason audit_deferred \
      --operator-id "$OPERATOR_ID" --evidence-ref "$run_dir/artifacts/rosbag2"
    echo "[AUDIT] 已跳过，后续可补填 $audit_path"
    return
  fi
  while true; do
    read -r -p "本次任务是否成功？[y/N]: " outcome
    case "${outcome,,}" in y|yes) outcome_args=(--success); break;; n|no|"") outcome_args=(--failure); break;; esac
    echo "请输入 y 或 n" >&2
  done
  read -r -p "终止原因（必填）: " reason
  [[ -n "$reason" ]] || reason=operator_unspecified
  read -r -p "是否发生安全事件？[y/N]: " safety
  read -r -p "是否有未记录的外部接管？[y/N]: " override
  safety_args=(); override_args=()
  [[ "${safety,,}" == y || "${safety,,}" == yes ]] && safety_args=(--safety-violation)
  [[ "${override,,}" == y || "${override,,}" == yes ]] && override_args=(--unlogged-external-override)
  /usr/bin/python3 "$ROOT_DIR/tools/finalize_episode_audit.py" --output "$audit_path" \
    --episode-id "$(basename "$run_dir")" "${outcome_args[@]}" --termination-reason "$reason" \
    --operator-id "$OPERATOR_ID" "${safety_args[@]}" "${override_args[@]}" \
    --evidence-ref "$run_dir/artifacts/rosbag2"
}

stop_tree() {
  local root="$1" signal="$2" child_pid
  for child_pid in $(pgrep -P "$root" 2>/dev/null || true); do
    stop_tree "$child_pid" "$signal"
  done
  kill -"$signal" "$root" 2>/dev/null || true
}

i=1
while [[ "$EPISODES" == 0 || "$i" -le "$EPISODES" ]]; do
  echo
  echo "========== READY: EPISODE $i =========="
  echo "按 Enter 开始本条；输入 q 后回车退出整个采集会话。"
  read -r start
  [[ "${start,,}" == q ]] && break
  [[ -z "$start" ]] || { echo "请按 Enter 开始，或输入 q 退出。"; continue; }
  echo "[RECORDING] episode $i 正在录制。按 Enter 停止并保存。"
  tmp="$(mktemp -d /tmp/teleop-capture.XXXXXX)"
  control="$tmp/stop"
  marker="$tmp/run_dir"
  bag_pid_file="$tmp/bag_pid"
  (
    export TELEOP_CAPTURE_CONTROL_FILE="$control" TELEOP_CAPTURE_RUN_MARKER="$marker" TELEOP_CAPTURE_BAG_PID_FILE="$bag_pid_file"
    export TELEOP_INTERACTIVE_AUDIT=false
    "$RUNEVIDENCE_BIN" run --domain robotics --runs-root "$RUN_ROOT" \
      --label "$EXPERIMENT_ID-$CONDITION_ID-episode-$i" \
      --input experiment_id="$EXPERIMENT_ID" --input condition_id="$CONDITION_ID" \
      --input operator_id="$OPERATOR_ID" --input task_id="$TASK_ID" -- bash "$RECORDER"
  ) &
  child=$!
  for _ in {1..100}; do [[ -s "$marker" ]] && break; sleep 0.1; done
  run_dir=""
  [[ -s "$marker" ]] && run_dir="$(<"$marker")"
  [[ -n "$run_dir" ]] || { echo "recorder did not publish run directory" >&2; kill "$child" 2>/dev/null || true; exit 3; }
  record_started=$SECONDS
  (
    while kill -0 "$child" 2>/dev/null; do
      bag="$run_dir/artifacts/rosbag2"
      bytes=0
      [[ -d "$bag" ]] && bytes="$(du -sb "$bag" 2>/dev/null | awk '{print $1}')"
      elapsed=$((SECONDS - record_started))
      printf '\r[RECORDING] elapsed %02dm%02ds | bag %s MB | press Enter to stop   ' \
        $((elapsed / 60)) $((elapsed % 60)) $((bytes / 1048576))
      sleep 1
    done
  ) &
  status_pid=$!
  read -r stop_key
  kill "$status_pid" 2>/dev/null || true
  wait "$status_pid" 2>/dev/null || true
  echo
  [[ -z "$stop_key" ]] || echo "已收到停止按键，停止并保存。"
  printf 'stop\n' > "$control"
  for _ in {1..20}; do [[ -s "$bag_pid_file" ]] && break; sleep 0.1; done
  if [[ -s "$bag_pid_file" ]]; then
    stop_tree "$(<"$bag_pid_file")" INT
  fi
  if [[ -s "$bag_pid_file" ]]; then
    bag_pid="$(<"$bag_pid_file")"
    kill -INT "$bag_pid" 2>/dev/null || true
  fi
  echo "[FINALIZING] 已发送停止命令，正在等待 rosbag 写入 metadata 和数据库，请勿关闭会话。"
  finalize_started=$SECONDS
  while kill -0 "$child" 2>/dev/null; do
    bag="$run_dir/artifacts/rosbag2"
    bytes=0
    [[ -d "$bag" ]] && bytes="$(du -sb "$bag" 2>/dev/null | awk '{print $1}')"
    elapsed=$((SECONDS - finalize_started))
    filled=$((elapsed % 21))
    bar=""
    for ((j=0; j<filled; j++)); do bar+="#"; done
    for ((j=filled; j<20; j++)); do bar+="."; done
    printf '\r[FINALIZING] [%s] %02dm%02ds | bag %s MB   ' "$bar" \
      $((elapsed / 60)) $((elapsed % 60)) $((bytes / 1048576))
    sleep 1
    if (( SECONDS - finalize_started > 60 )); then
      echo
      echo "[ERROR] rosbag 收尾超过 60 秒，强制停止剩余进程。" >&2
      stop_tree "$child" TERM
      break
    fi
  done
  wait "$child"
  echo
  echo "[SAVED] rosbag 已完成收尾：$run_dir/artifacts/rosbag2"
  finalize_audit "$run_dir"
  echo "[READY] episode $i 已完成，下一条可直接按回车开始。"
  rm -f "$control" "$marker" "$bag_pid_file"
  rmdir "$tmp"
  i=$((i + 1))
done
echo "ALL_EPISODES_COMPLETE"
echo "可重新开始采集：bash $ROOT_DIR/scripts/run_manual_episode.sh"
echo "安全关闭整个会话：bash $ROOT_DIR/scripts/stop_capture_session.sh"
