#!/usr/bin/env bash
# Verify only the R J5 v4 candidate through the simulator-only route.
# This script never starts or addresses a real robot route.
# ROS Jazzy's setup scripts intentionally inspect optional unset variables.
# Enable nounset only after those scripts have been sourced.
set -eo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS2CLI_DISABLE_DAEMON=1

config="alignment/calibrations/openarm_isaac_replay_calibration_v4_candidate_right_j5.json"
output_dir="alignment/results/isaac_only_right_j5_v4_candidate"
[[ -f "$config" ]] || { echo "REFUSED: missing $config" >&2; exit 2; }
pgrep -af '[d]ual_target_command_router' >/dev/null && {
  echo "REFUSED: existing router is running" >&2; exit 2;
}

ros2 service call /openarm/isaac_gap/enable_right_j5_v4_candidate_replay \
  std_srvs/srv/Trigger '{}'
sleep 2
status="$(ros2 service call /openarm/isaac_gap/status std_srvs/srv/Trigger '{}')"
printf '%s\n' "$status"
[[ "$status" == *"compensation_replay=True"* ]] || {
  echo "REFUSED: candidate was not armed; reload the deployed Isaac daemon" >&2; exit 2;
}

mkdir -p "$output_dir"
/usr/bin/python3 alignment/dual_target_command_router.py --ros-args -p enable_real:=false \
  >"$output_dir/router.log" 2>&1 &
router_pid=$!
cleanup() {
  if kill -0 "$router_pid" 2>/dev/null; then kill -TERM "$router_pid" 2>/dev/null || true; fi
  wait "$router_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
sleep 2
kill -0 "$router_pid" || { cat "$output_dir/router.log" >&2; exit 1; }

/usr/bin/python3 alignment/measure_sim_only_compensated_replay.py \
  --config "$config" --joint openarm_right_joint5 --target-rad 0.02 --hold-s 3 \
  --tolerance-rad 0.01 --discovery-timeout-s 12 \
  --output "$output_dir/openarm_right_joint5.json"

echo "OPENARM_ISAAC_ONLY_RIGHT_J5_V4_CANDIDATE=PASS output=$output_dir/openarm_right_joint5.json"
