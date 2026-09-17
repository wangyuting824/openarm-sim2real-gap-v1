#!/usr/bin/env bash
# Can command hardware.  Only the explicitly authorized J7 dynamic pilot is
# accepted here; other joints require their own manifest and authorization.
set -eo pipefail

trial_id="${1:-}"
if [[ "$trial_id" != "openarm_real_sim_right_j7_dynamic_pilot_v1" ]]; then
  echo "Usage: $0 openarm_real_sim_right_j7_dynamic_pilot_v1" >&2
  exit 64
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-/tmp/openarm_ros_logs}"
mkdir -p "$ROS_LOG_DIR"

if pgrep -af '^/usr/bin/python3 .*alignment/dual_target_command_router\.py' >/dev/null; then
  echo "REFUSED: a dual-target router is already running." >&2
  exit 2
fi

# Raw dynamics require identical canonical targets on both endpoints.  The
# existing static replay bridge must therefore be disabled before motion.
status="$(ros2 service call /openarm/isaac_gap/status std_srvs/srv/Trigger '{}')"
printf '%s\n' "$status"
if [[ "$status" != *"state=True bridge=True compensation_replay=False"* ]]; then
  echo "REFUSED: Isaac state/bridge unavailable or static replay still enabled." >&2
  exit 3
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
  if kill -0 "$router_pid" 2>/dev/null; then
    kill -TERM "$router_pid" 2>/dev/null || true
  fi
  wait "$router_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 2
if ! kill -0 "$router_pid"; then
  cat "$results_dir/router.log" >&2 || true
  exit 4
fi

/usr/bin/python3 alignment/measure_real_sim_dynamic_identification.py \
  --trial-id "$trial_id" \
  --joint openarm_right_joint7 \
  --require-real \
  --output "$results_dir/raw.json"

/usr/bin/python3 alignment/analyze_dynamic_gap.py \
  --input "$results_dir/raw.json" \
  --output "$results_dir/dynamic_metrics.json"

echo "OPENARM_REAL_SIM_DYNAMIC_PILOT=PASS output=$results_dir"
