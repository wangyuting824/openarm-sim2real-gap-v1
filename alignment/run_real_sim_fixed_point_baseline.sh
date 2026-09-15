#!/usr/bin/env bash
# Execute the explicit 14-axis fixed-point baseline manifest.
# This script can command physical hardware.  It deliberately requires the
# manifest trial ID as a command-line value; do not invoke it without a fresh
# operator authorization for that ID.
set -eo pipefail

trial_id="${1:-}"
case "$trial_id" in
  openarm_real_sim_bimanual_fixed_0p1_baseline_v1)
    joints=(
      openarm_left_joint1 openarm_left_joint2 openarm_left_joint3
      openarm_left_joint4 openarm_left_joint5 openarm_left_joint6 openarm_left_joint7
      openarm_right_joint1 openarm_right_joint2 openarm_right_joint3
      openarm_right_joint4 openarm_right_joint5 openarm_right_joint6 openarm_right_joint7
    )
    ;;
  openarm_real_sim_bimanual_fixed_0p1_full14_v2)
    joints=(
      openarm_left_joint1 openarm_left_joint2 openarm_left_joint3
      openarm_left_joint4 openarm_left_joint5 openarm_left_joint6 openarm_left_joint7
      openarm_right_joint1 openarm_right_joint2 openarm_right_joint3
      openarm_right_joint4 openarm_right_joint5 openarm_right_joint6 openarm_right_joint7
    )
    ;;
  openarm_real_sim_bimanual_fixed_0p1_remaining10_v2)
    joints=(
      openarm_left_joint5 openarm_left_joint6 openarm_left_joint7
      openarm_right_joint1 openarm_right_joint2 openarm_right_joint3
      openarm_right_joint4 openarm_right_joint5 openarm_right_joint6 openarm_right_joint7
    )
    ;;
  *)
    echo "Usage: $0 {openarm_real_sim_bimanual_fixed_0p1_baseline_v1|openarm_real_sim_bimanual_fixed_0p1_full14_v2|openarm_real_sim_bimanual_fixed_0p1_remaining10_v2}" >&2
    exit 64
    ;;
esac

cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"

if pgrep -af '^/usr/bin/python3 .*alignment/dual_target_command_router\.py' >/dev/null; then
  echo "Refusing to start: a dual-target router is already running." >&2
  exit 2
fi

results_dir="alignment/results/$trial_id"
mkdir -p "$results_dir"
/usr/bin/python3 alignment/dual_target_command_router.py --ros-args \
  -p enable_real:=true \
  -p real_authorization_id:="$trial_id" \
  -p real_publish_hz:=50.0 \
  -p max_delta_rad:=0.15 \
  -p real_state_max_age_s:=0.25 \
  >"$results_dir/router.log" 2>&1 &
router_pid=$!
cleanup() {
  kill "$router_pid" 2>/dev/null || true
  wait "$router_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 2
if ! kill -0 "$router_pid" 2>/dev/null; then
  cat "$results_dir/router.log" >&2 || true
  exit 1
fi

for joint in "${joints[@]}"; do
  echo "BASELINE_JOINT=$joint"
  /usr/bin/python3 alignment/measure_real_sim_fixed_point_baseline.py \
    --trial-id "$trial_id" \
    --joint "$joint" \
    --target-rad 0.1 \
    --max-excursion-rad 0.15 \
    --hold-s 3.0 \
    --return-hold-s 1.0 \
    --sim-tolerance-rad 0.01 \
    --output "$results_dir/${joint}.json"
  sleep 1
done

echo "OPENARM_REAL_SIM_FIXED_POINT_BASELINE=PASS output=$results_dir"
