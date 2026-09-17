#!/usr/bin/env bash
# Start the named 13-axis trial outside an interactive shell's process group.
# The runner itself enforces the power-cycle attestation and hardware gates.
set -euo pipefail
trial_id="${1:-}"
if [[ "$trial_id" != "openarm_static_independent_session_v3_remaining13" ]]; then
  echo "Usage: $0 openarm_static_independent_session_v3_remaining13" >&2
  exit 64
fi
cd "$(dirname "${BASH_SOURCE[0]}")/.."
results_dir="alignment/results/$trial_id"
mkdir -p "$results_dir"
if pgrep -f '^/usr/bin/python3 .*alignment/dual_target_command_router\.py( |$)' >/dev/null; then
  echo "REFUSED: real/sim router already running" >&2
  exit 2
fi
setsid env OPENARM_INDEPENDENT_POWER_CYCLE_CONFIRMED=1 ROS_LOG_DIR=/tmp/openarm_ros_logs \
  bash alignment/run_real_sim_offset_identification.sh "$trial_id" \
  </dev/null >"$results_dir/trial.log" 2>&1 &
pid=$!
printf '%s\n' "$pid" >"$results_dir/runner.pid"
echo "OPENARM_STATIC_REMAINING13_STARTED pid=$pid output=$results_dir"
