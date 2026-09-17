#!/usr/bin/env bash
# Authorized physical orchestration: replace hold-pose bringup with normal
# activation-time return_to_zero(), then launch the frozen-v4 full14 trial.
set -eo pipefail
trial_id="${1:-}"
[[ "$trial_id" == "openarm_static_independent_session_v4_homed_full14" ]] || { echo "Usage: $0 openarm_static_independent_session_v4_homed_full14" >&2; exit 64; }
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
results_dir="alignment/results/$trial_id"
mkdir -p "$results_dir"
if pgrep -f '^/usr/bin/python3 .*alignment/dual_target_command_router\.py( |$)' >/dev/null; then echo 'REFUSED: router active' >&2; exit 2; fi
old_launches="$(pgrep -f '^/usr/bin/python3 /opt/ros/jazzy/bin/ros2 launch openarm_bringup' || true)"
for old_pid in $old_launches; do
  old_pgid="$(ps -o pgid= -p "$old_pid" | tr -d ' ')"
  [[ -n "$old_pgid" ]] || { echo "REFUSED: no process group for old launch $old_pid" >&2; exit 2; }
  kill -TERM -- "-$old_pgid"
done
for _ in $(seq 1 30); do
  pgrep -f '^/usr/bin/python3 /opt/ros/jazzy/bin/ros2 launch openarm_bringup' >/dev/null || break
  sleep 1
done
pgrep -f '^/usr/bin/python3 /opt/ros/jazzy/bin/ros2 launch openarm_bringup' >/dev/null && { echo 'REFUSED: old bringup did not exit' >&2; exit 2; }
setsid env -u OPENARM_SKIP_RETURN_TO_ZERO ROS_LOG_DIR=/tmp/openarm_ros_logs \
  bash alignment/start_real_openarm.sh </dev/null >"$results_dir/real_bringup.log" 2>&1 &
bringup_pid=$!
printf '%s\n' "$bringup_pid" >"$results_dir/bringup.pid"
for _ in $(seq 1 30); do
  grep -q 'OpenArm V10 activated' "$results_dir/real_bringup.log" 2>/dev/null && break
  sleep 1
done
grep -q 'Returning to zero position' "$results_dir/real_bringup.log" || { echo 'REFUSED: no return-to-zero evidence' >&2; exit 2; }
grep -q 'OpenArm V10 activated' "$results_dir/real_bringup.log" || { echo 'REFUSED: activation not confirmed' >&2; exit 2; }
/usr/bin/python3 alignment/real_sim_gap_agent.py --duration-s 5 \
  --output "$results_dir/post_bringup_health.json"
/usr/bin/python3 alignment/check_real_arm_zero_settle.py --duration-s 3 --tolerance-rad 0.03 \
  --output "$results_dir/zero_settle_gate.json"
setsid env OPENARM_HOMED_START_CONFIRMED=1 ROS_LOG_DIR=/tmp/openarm_ros_logs \
  bash alignment/run_real_sim_offset_identification.sh "$trial_id" </dev/null >"$results_dir/trial.log" 2>&1 &
runner_pid=$!
printf '%s\n' "$runner_pid" >"$results_dir/runner.pid"
echo "OPENARM_STATIC_HOMED_FULL14_STARTED bringup=$bringup_pid runner=$runner_pid output=$results_dir"
