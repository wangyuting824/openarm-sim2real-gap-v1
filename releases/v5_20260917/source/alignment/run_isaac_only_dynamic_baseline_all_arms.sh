#!/usr/bin/env bash
# Record unmodified Isaac-only dynamic baselines for every arm joint.  The
# temporary router is permanently real-disabled; no hardware command is sent.
set -eo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export ROS_AUTOMATIC_DISCOVERY_RANGE="${ROS_AUTOMATIC_DISCOVERY_RANGE:-SUBNET}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-/tmp/openarm_ros_logs}"
mkdir -p "$ROS_LOG_DIR"

if pgrep -af '^/usr/bin/python3 .*alignment/dual_target_command_router\.py' >/dev/null; then
  echo "REFUSED: router already running" >&2; exit 2
fi
status="$(ros2 service call /openarm/isaac_gap/status std_srvs/srv/Trigger '{}')"
printf '%s\n' "$status"
if [[ "$status" != *"state=True bridge=True compensation_replay=False"* ]]; then
  echo "REFUSED: all-axis raw dynamic baseline needs bridge/state and disabled static replay" >&2; exit 3
fi

out="alignment/results/openarm_isaac_only_dynamic_baseline_all14_v1"
mkdir -p "$out"
/usr/bin/python3 alignment/dual_target_command_router.py --ros-args -p enable_real:=false >"$out/router.log" 2>&1 &
pid=$!
cleanup() { kill -TERM "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
sleep 2
kill -0 "$pid"

joints=(
  openarm_left_joint1 openarm_left_joint2 openarm_left_joint3 openarm_left_joint4
  openarm_left_joint5 openarm_left_joint6 openarm_left_joint7
  openarm_right_joint1 openarm_right_joint2 openarm_right_joint3 openarm_right_joint4
  openarm_right_joint5 openarm_right_joint6 openarm_right_joint7
)
for joint in "${joints[@]}"; do
  echo "DYNAMIC_BASELINE_JOINT=$joint"
  safe="${joint#openarm_}"
  /usr/bin/python3 alignment/measure_real_sim_dynamic_identification.py \
    --trial-id "openarm_isaac_only_dynamic_baseline_all14_v1_${safe}" \
    --joint "$joint" --output "$out/${safe}_raw.json"
  /usr/bin/python3 alignment/analyze_dynamic_gap.py \
    --input "$out/${safe}_raw.json" --output "$out/${safe}_dynamic_metrics.json"
done
/usr/bin/python3 alignment/summarize_isaac_dynamic_baselines.py \
  --input-dir "$out" --output "$out/all14_summary.json"
echo "OPENARM_ISAAC_ONLY_DYNAMIC_BASELINE_ALL14=PASS output=$out"
