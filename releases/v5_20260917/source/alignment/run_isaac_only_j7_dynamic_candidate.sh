#!/usr/bin/env bash
# Measure the currently applied J7 live Isaac drive candidate.  The child
# router is permanently simulator-only.
set -eo pipefail
candidate_id="${1:?Usage: $0 CANDIDATE_ID [fit|validation]}"
mode="${2:-fit}"
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
  echo "REFUSED: router already running" >&2; exit 2
fi
status="$(ros2 service call /openarm/isaac_gap/status std_srvs/srv/Trigger '{}')"
printf '%s\n' "$status"
if [[ "$status" != *"state=True bridge=True compensation_replay=False"* ]]; then
  echo "REFUSED: dynamic baseline needs bridge/state and disabled static replay" >&2; exit 3
fi
case "$mode" in
  fit) steps=(0.025 -0.025 0.05 -0.05); suffix="" ;;
  validation) steps=(0.015 -0.015 0.04 -0.04); suffix="_validation" ;;
  *) echo "REFUSED: mode must be fit or validation" >&2; exit 2 ;;
esac
out="alignment/results/openarm_isaac_only_right_j7_dynamic_${candidate_id}${suffix}"
mkdir -p "$out"
/usr/bin/python3 alignment/dual_target_command_router.py --ros-args -p enable_real:=false >"$out/router.log" 2>&1 &
pid=$!
cleanup() { kill -TERM "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
sleep 2
kill -0 "$pid"
/usr/bin/python3 alignment/measure_real_sim_dynamic_identification.py \
  --trial-id "openarm_isaac_only_right_j7_dynamic_${candidate_id}" \
  --joint openarm_right_joint7 --step-rad "${steps[@]}" --output "$out/raw.json"
/usr/bin/python3 alignment/analyze_dynamic_gap.py --input "$out/raw.json" --output "$out/dynamic_metrics.json"
echo "OPENARM_ISAAC_ONLY_J7_DYNAMIC=PASS candidate=$candidate_id output=$out"
