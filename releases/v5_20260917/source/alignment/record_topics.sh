#!/usr/bin/env bash
# Record only explicitly supplied ROS topics. This script never publishes commands.
set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "用法: $0 <session_dir_or_id> <record_name> <duration_sec> <topic> [topic ...]" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_DIR="$1"
RECORD_NAME="$2"
DURATION="$3"
shift 3
TOPICS=("$@")

if [[ "$SESSION_DIR" != /* ]]; then
  SESSION_DIR="$ROOT_DIR/alignment/results/isaacsim_migration/$SESSION_DIR"
fi
mkdir -p "$SESSION_DIR"
source /opt/ros/jazzy/setup.bash
source "$ROOT_DIR/install/setup.bash"

mapfile -t AVAILABLE < <(ros2 topic list)
for topic in "${TOPICS[@]}"; do
  if ! printf '%s\n' "${AVAILABLE[@]}" | grep -Fxq "$topic"; then
    echo "话题不存在，未开始录包: $topic" >&2
    exit 3
  fi
done

set +e
timeout -s INT "${DURATION}s" ros2 bag record \
  -o "$SESSION_DIR/$RECORD_NAME" "${TOPICS[@]}"
rc=$?
set -e
if [[ $rc -ne 0 && $rc -ne 124 && $rc -ne 130 ]]; then
  exit "$rc"
fi
printf '%s\n' "$SESSION_DIR/$RECORD_NAME"
