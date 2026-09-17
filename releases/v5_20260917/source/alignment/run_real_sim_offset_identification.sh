#!/usr/bin/env bash
# Can command hardware. Run only with the exact named authorization below.
set -eo pipefail
trial_id="${1:-}"
resume="${2:-}"
is_right_j5_v4_holdout=false
is_remaining13_v4_holdout=false
is_homed_full14_v4_holdout=false
if [[ "$trial_id" == "openarm_right_j5_v4_independent_power_holdout_v1" || "$trial_id" == "openarm_right_j5_v4_independent_power_holdout_v2" ]]; then
  is_right_j5_v4_holdout=true
fi
if [[ "$trial_id" == "openarm_static_independent_session_v3_remaining13" ]]; then
  is_remaining13_v4_holdout=true
fi
if [[ "$trial_id" == "openarm_static_independent_session_v4_homed_full14" ]]; then
  is_homed_full14_v4_holdout=true
fi
if [[ "$trial_id" != "openarm_real_sim_bimanual_offset_identification_v1" && "$trial_id" != "openarm_real_sim_bimanual_offset_identification_v2" && "$trial_id" != "openarm_real_sim_bimanual_offset_identification_v3" && "$trial_id" != "openarm_real_sim_right_j6_j7_offset_identification_retry_v4" && "$trial_id" != "openarm_real_sim_right_j7_offset_independent_replay_v5" && "$trial_id" != "openarm_static_independent_session_v1" && "$trial_id" != "openarm_static_independent_session_v2" && "$trial_id" != "openarm_static_independent_session_v3_remaining13" && "$trial_id" != "openarm_static_independent_session_v4_homed_full14" && "$trial_id" != "openarm_right_j5_v4_independent_power_holdout_v1" && "$trial_id" != "openarm_right_j5_v4_independent_power_holdout_v2" ]] || [[ -n "$resume" && "$resume" != "--remaining-13" && "$resume" != "--from-left-j4" && "$resume" != "--from-left-j6" && "$resume" != "--from-right-j3" ]]; then
  echo "Usage: $0 <registered_trial_id> [--remaining-13|--from-left-j4|--from-left-j6|--from-right-j3]" >&2; exit 64
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
joints=(openarm_left_joint1 openarm_left_joint2 openarm_left_joint3 openarm_left_joint4 openarm_left_joint5 openarm_left_joint6 openarm_left_joint7 openarm_right_joint1 openarm_right_joint2 openarm_right_joint3 openarm_right_joint4 openarm_right_joint5 openarm_right_joint6 openarm_right_joint7)
if [[ "$trial_id" == "openarm_real_sim_right_j6_j7_offset_identification_retry_v4" ]]; then
  joints=(openarm_right_joint6 openarm_right_joint7)
fi
if [[ "$trial_id" == "openarm_real_sim_right_j7_offset_independent_replay_v5" ]]; then
  joints=(openarm_right_joint7)
fi
if "$is_right_j5_v4_holdout"; then
  joints=(openarm_right_joint5)
fi
if "$is_remaining13_v4_holdout"; then
  joints=(openarm_left_joint1 openarm_left_joint2 openarm_left_joint3 openarm_left_joint4 openarm_left_joint5 openarm_left_joint6 openarm_left_joint7 openarm_right_joint1 openarm_right_joint2 openarm_right_joint3 openarm_right_joint4 openarm_right_joint6 openarm_right_joint7)
fi
if [[ "$resume" == "--remaining-13" ]]; then joints=("${joints[@]:1}"); fi
if [[ "$resume" == "--from-left-j4" ]]; then joints=("${joints[@]:3}"); fi
if [[ "$resume" == "--from-left-j6" ]]; then joints=("${joints[@]:5}"); fi
if [[ "$resume" == "--from-right-j3" ]]; then joints=("${joints[@]:9}"); fi
if pgrep -af '^/usr/bin/python3 .*alignment/dual_target_command_router\.py' >/dev/null; then
  echo "Refusing to start: a dual-target router is already running." >&2; exit 2
fi
results_dir="alignment/results/$trial_id"
mkdir -p "$results_dir"
router_max_delta_rad=0.15
measurement_bounds=()
if "$is_right_j5_v4_holdout"; then
  router_max_delta_rad=0.10
  measurement_bounds+=(--max-excursion-rad 0.10)
  if [[ "${OPENARM_INDEPENDENT_POWER_CYCLE_CONFIRMED:-}" != "1" ]]; then
    echo "REFUSED: set OPENARM_INDEPENDENT_POWER_CYCLE_CONFIRMED=1 only after the declared fresh physical power cycle and safety checks." >&2
    exit 2
  fi
  /usr/bin/python3 alignment/real_sim_gap_agent.py --duration-s 5 \
    --output "$results_dir/preflight_real_sim_health.json"
fi
if "$is_remaining13_v4_holdout"; then
  if [[ "${OPENARM_INDEPENDENT_POWER_CYCLE_CONFIRMED:-}" != "1" ]]; then
    echo "REFUSED: set OPENARM_INDEPENDENT_POWER_CYCLE_CONFIRMED=1 only after the declared fresh physical power cycle and safety checks." >&2
    exit 2
  fi
  /usr/bin/python3 alignment/real_sim_gap_agent.py --duration-s 5 \
    --output "$results_dir/preflight_real_sim_health.json"
fi
if "$is_homed_full14_v4_holdout"; then
  if [[ "${OPENARM_HOMED_START_CONFIRMED:-}" != "1" ]]; then
    echo "REFUSED: this trial requires the orchestrator to complete and attest the authorized return-to-zero startup." >&2
    exit 2
  fi
  /usr/bin/python3 alignment/real_sim_gap_agent.py --duration-s 5 \
    --output "$results_dir/preflight_real_sim_health.json"
fi
/usr/bin/python3 alignment/dual_target_command_router.py --ros-args \
  -p enable_real:=true -p real_authorization_id:="$trial_id" -p real_publish_hz:=50.0 \
  -p max_delta_rad:="$router_max_delta_rad" -p real_state_max_age_s:=0.25 >"$results_dir/router.log" 2>&1 &
router_pid=$!
cleanup() {
  if kill -0 "$router_pid" 2>/dev/null; then kill -TERM "$router_pid" 2>/dev/null || true; fi
  wait "$router_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
sleep 2
kill -0 "$router_pid" || { cat "$results_dir/router.log" >&2; exit 1; }
for joint in "${joints[@]}"; do
  echo "IDENTIFICATION_JOINT=$joint"
  extra_args=()
  if [[ "$trial_id" == "openarm_static_independent_session_v2" ]]; then
    extra_args+=(--sim-replay-calibration alignment/calibrations/openarm_isaac_replay_calibration_v3.json)
  fi
  if "$is_remaining13_v4_holdout"; then
    extra_args+=(--sim-replay-calibration alignment/calibrations/openarm_isaac_replay_calibration_v4_candidate_right_j5.json)
  fi
  if "$is_homed_full14_v4_holdout"; then
    extra_args+=(--sim-replay-calibration alignment/calibrations/openarm_isaac_replay_calibration_v4_candidate_right_j5.json)
  fi
  if "$is_right_j5_v4_holdout"; then
    extra_args+=(--sim-replay-calibration alignment/calibrations/openarm_isaac_replay_calibration_v4_candidate_right_j5.json)
  fi
  if [[ "$joint" == "openarm_left_joint4" || "$joint" == "openarm_right_joint4" ]]; then
    extra_args+=(--relative-waypoints "0.05,0,0.10,0.05,0")
  fi
  /usr/bin/python3 alignment/measure_real_sim_offset_identification.py \
    --trial-id "$trial_id" --joint "$joint" --output "$results_dir/${joint}.json" \
    "${measurement_bounds[@]}" "${extra_args[@]}"
  sleep 1
done
if "$is_right_j5_v4_holdout"; then
  /usr/bin/python3 alignment/analyze_right_j5_v4_independent_holdout.py \
    --input "$results_dir/openarm_right_joint5.json" \
    --output "$results_dir/independent_power_holdout_summary.json"
fi
echo "OPENARM_REAL_SIM_OFFSET_IDENTIFICATION=PASS output=$results_dir"
