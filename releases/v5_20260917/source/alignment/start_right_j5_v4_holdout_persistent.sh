#!/usr/bin/env bash
# Start a named physical trial detached from an interactive tool timeout.
# The caller still needs the exact new authorization and power-cycle attestation.
set -euo pipefail
trial_id="${1:-}"
if [[ "$trial_id" != "openarm_right_j5_v4_independent_power_holdout_v2" ]]; then
  echo "Usage: $0 openarm_right_j5_v4_independent_power_holdout_v2" >&2
  exit 64
fi
cd "$(dirname "${BASH_SOURCE[0]}")/.."
results_dir="alignment/results/$trial_id"
mkdir -p "$results_dir"
if pgrep -af '[d]ual_target_command_router' >/dev/null; then
  echo "REFUSED: real/sim router already running" >&2
  exit 2
fi
setsid env OPENARM_INDEPENDENT_POWER_CYCLE_CONFIRMED=1 ROS_LOG_DIR=/tmp/openarm_ros_logs \
  bash alignment/run_real_sim_offset_identification.sh "$trial_id" \
  </dev/null >"$results_dir/trial.log" 2>&1 &
pid=$!
printf '%s\n' "$pid" >"$results_dir/runner.pid"
echo "OPENARM_RIGHT_J5_V4_HOLDOUT_STARTED pid=$pid output=$results_dir"
