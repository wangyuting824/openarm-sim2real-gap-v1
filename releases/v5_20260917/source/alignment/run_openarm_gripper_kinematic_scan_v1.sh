#!/usr/bin/env bash
# Can command real grippers. Use only for the exact manifest authorization.
set -eo pipefail
trial_id="${1:-}"
[[ "$trial_id" == "openarm_gripper_kinematic_scan_v1" ]] || { echo "Usage: $0 openarm_gripper_kinematic_scan_v1" >&2; exit 64; }
[[ "${OPENARM_GRIPPER_SCAN_AUTHORIZED:-}" == "$trial_id" ]] || { echo "REFUSED: set OPENARM_GRIPPER_SCAN_AUTHORIZED=$trial_id only after the named safety authorization." >&2; exit 2; }
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
results_dir="alignment/results/$trial_id"
mkdir -p "$results_dir"
if ps -eo pid=,args= | awk '$2=="/usr/bin/python3" && $3 ~ /alignment\\/dual_target_command_router\\.py$/ {found=1} END {exit !found}'; then
  echo "REFUSED: existing dual-target router found." >&2; exit 2
fi
/usr/bin/python3 alignment/real_sim_gap_agent.py --duration-s 5 --output "$results_dir/preflight_real_sim_health.json"
/usr/bin/python3 alignment/dual_target_command_router.py --ros-args \
  -p enable_real:=true -p real_authorization_id:="$trial_id" -p real_publish_hz:=50.0 \
  -p max_delta_rad:=0.025 -p real_state_max_age_s:=0.25 >"$results_dir/router.log" 2>&1 &
router_pid=$!
cleanup() { kill -TERM "$router_pid" 2>/dev/null || true; wait "$router_pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
sleep 5
kill -0 "$router_pid" || { cat "$results_dir/router.log" >&2; exit 1; }
for side in left right; do
  /usr/bin/python3 alignment/measure_openarm_gripper_kinematics.py \
    --trial-id "$trial_id" --side "$side" --output "$results_dir/${side}.json"
done
/usr/bin/python3 alignment/analyze_openarm_gripper_kinematics.py \
  --input-dir "$results_dir" --output "$results_dir/summary.json"
echo "OPENARM_GRIPPER_KINEMATIC_SCAN=PASS output=$results_dir"
