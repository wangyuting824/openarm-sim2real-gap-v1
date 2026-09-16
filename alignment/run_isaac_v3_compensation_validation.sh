#!/usr/bin/env bash
# Run the complete 14-axis v3 Isaac-only replay validation.
# It never enables the real route and terminates its temporary sim-only router.
set -eo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS2CLI_DISABLE_DAEMON=1

config="alignment/calibrations/openarm_isaac_replay_calibration_v3.json"
output_dir="alignment/results/sim_only_compensated_replay_v3_full14"
if [[ ! -f "$config" ]]; then
  echo "REFUSED: v3 calibration is missing: $config" >&2
  exit 2
fi
if pgrep -af '[d]ual_target_command_router' >/dev/null; then
  echo "REFUSED: an existing router is running; inspect it before validation." >&2
  pgrep -af '[d]ual_target_command_router' >&2
  exit 2
fi

echo "Enabling Isaac-only compensation replay."
ros2 service call /openarm/isaac_gap/enable_compensation_replay std_srvs/srv/Trigger '{}'
sleep 2
status="$(ros2 service call /openarm/isaac_gap/status std_srvs/srv/Trigger '{}')"
printf '%s\n' "$status"
if [[ "$status" != *"compensation_replay=True"* ]]; then
  echo "REFUSED: daemon did not report compensation_replay=True; reload the Isaac daemon after v3 deployment." >&2
  exit 2
fi

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
OPENARM_COMPENSATION_CONFIG="$config" \
OPENARM_COMPENSATION_OUTPUT_DIR="$output_dir/batch" \
  bash alignment/run_sim_only_compensated_replay_batch.sh

/usr/bin/python3 - "$output_dir" <<'PY'
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
records = [json.loads(path.read_text(encoding="utf-8"))
           for path in sorted(directory.rglob("openarm_*_joint*.json"))]
summary = {
    "kind": "openarm_isaac_v3_full14_compensated_replay_validation",
    "calibration": "openarm_isaac_replay_calibration_v3.json",
    "joint_count": len(records),
    "passed_joint_count": sum(x.get("passed", False) for x in records),
    "all_passed": len(records) == 14 and all(x.get("passed", False) for x in records),
    "all_receipts_sim_only": all(x.get("all_receipts_sim_only", False) for x in records),
    "max_target_error_rad": max(abs(x["target_error_rad"]) for x in records),
    "max_return_error_rad": max(abs(x["return_error_rad"]) for x in records),
}
(directory / "full14_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
if not (summary["all_passed"] and summary["all_receipts_sim_only"]):
    raise SystemExit(2)
PY

echo "OPENARM_ISAAC_V3_FULL14_REPLAY=PASS output=$output_dir/full14_summary.json"
