#!/usr/bin/env bash
# A simulator-only, visually observable v3 bridge check.  It never enables real routing.
set -eo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"

if pgrep -af '[d]ual_target_command_router' >/dev/null; then
  echo "REFUSED: an existing router is running." >&2
  exit 2
fi

output="alignment/results/sim_only_compensated_replay_v3_visible_right_j5.json"
/usr/bin/python3 alignment/dual_target_command_router.py --ros-args -p enable_real:=false >"${output%.json}.router.log" 2>&1 &
router_pid=$!
cleanup() {
  if kill -0 "$router_pid" 2>/dev/null; then kill -TERM "$router_pid" 2>/dev/null || true; fi
  wait "$router_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
sleep 2

/usr/bin/python3 alignment/measure_sim_only_compensated_replay.py \
  --config alignment/calibrations/openarm_isaac_replay_calibration_v3.json \
  --joint openarm_right_joint5 --target-rad 0.10 --hold-s 4 \
  --tolerance-rad 0.01 --output "$output"
