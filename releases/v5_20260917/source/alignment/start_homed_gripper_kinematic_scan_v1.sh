#!/usr/bin/env bash
# Physical recovery plus the separately authorized gripper scan.
set -eo pipefail
[[ "${OPENARM_RETURN_ZERO_AUTHORIZED:-}" == "openarm_real_bringup_enable_return_zero_recovery_v1" ]] || { echo 'REFUSED: missing return-zero authorization token' >&2; exit 2; }
[[ "${OPENARM_GRIPPER_SCAN_AUTHORIZED:-}" == "openarm_gripper_kinematic_scan_v1" ]] || { echo 'REFUSED: missing gripper-scan authorization token' >&2; exit 2; }
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
trial_id=openarm_gripper_kinematic_scan_v1
results_dir="alignment/results/$trial_id"
mkdir -p "$results_dir"
if pgrep -af '^/usr/bin/python3 .*alignment/dual_target_command_router\.py' >/dev/null; then
  echo 'REFUSED: a real command router is already active' >&2; exit 2
fi
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
  bash alignment/start_real_openarm.sh </dev/null >"$results_dir/real_bringup_for_gripper.log" 2>&1 &
bringup_pid=$!
printf '%s\n' "$bringup_pid" >"$results_dir/bringup_for_gripper.pid"
for _ in $(seq 1 35); do
  grep -q 'Reached zero position' "$results_dir/real_bringup_for_gripper.log" 2>/dev/null && break
  sleep 1
done
grep -q 'OpenArm V10 activated' "$results_dir/real_bringup_for_gripper.log" || { echo 'REFUSED: activation evidence absent' >&2; exit 2; }
grep -q 'Reached zero position' "$results_dir/real_bringup_for_gripper.log" || { echo 'REFUSED: return-to-zero evidence absent' >&2; exit 2; }
/usr/bin/python3 alignment/check_real_arm_zero_settle.py --duration-s 3 --tolerance-rad 0.03 \
  --output "$results_dir/zero_settle_before_gripper.json"
python3 - <<'PY' "$results_dir/zero_settle_before_gripper.json"
import json, sys
d=json.load(open(sys.argv[1]))
if not d.get('passed'):
    raise SystemExit('REFUSED: zero settle gate failed')
PY
exec bash alignment/run_openarm_gripper_kinematic_scan_v1.sh "$trial_id"
