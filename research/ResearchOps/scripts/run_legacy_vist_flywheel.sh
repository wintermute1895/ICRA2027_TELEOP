#!/usr/bin/env bash
# Read-only VIST legacy replay: export one bag, score, mine hard cases, register.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 LEGACY_VIST_EPISODE_DIR OUTPUT_DIR" >&2
  exit 2
fi

episode_dir=$1
output_dir=$2
workspace=/mnt/F/ICRA2027_TELEOP
research_ops=/mnt/F/Obsidian/Vault/ResearchOps
episode_id="legacy_vist_$(basename "$episode_dir")"

[[ -d "$episode_dir" ]] || { echo "not a directory: $episode_dir" >&2; exit 2; }
mkdir -p "$output_dir/reports"

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 "$research_ops/tools/export_legacy_vist_episode.py" \
  --bag "$episode_dir" --episode-id "$episode_id" --output "$output_dir/$episode_id.jsonl"

python3 "$workspace/tools/score_episode_data_quality.py" \
  --episode "$output_dir/$episode_id.jsonl" \
  --config "$research_ops/config/legacy_vist_rgb_only_quality_gate.yaml" \
  --output "$output_dir/reports/data_quality.json"

set +e
python3 "$workspace/tools/evaluate_trajectory_quality.py" \
  --episode "$output_dir/$episode_id.jsonl" \
  --output "$output_dir/reports/trajectory_quality.json"
trajectory_status=$?
set -e

python3 "$workspace/tools/mine_hard_cases.py" \
  --trajectory-report "$output_dir/reports/trajectory_quality.json" \
  --output "$output_dir/reports/hard_cases.json"
python3 "$workspace/tools/build_episode_registry.py" \
  --root "$output_dir/reports" --output "$output_dir/legacy_episode_registry.jsonl"

echo "Legacy flywheel complete: $output_dir (trajectory gate exit=$trajectory_status; review is retained)"
