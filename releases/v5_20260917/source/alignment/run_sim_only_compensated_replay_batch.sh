#!/usr/bin/env bash
# Verify enabled replay candidates not already exercised by a separate smoke
# test. The router must already be running with enable_real=false.
set -eo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"

config="${OPENARM_COMPENSATION_CONFIG:-alignment/calibrations/openarm_isaac_replay_calibration_v3.json}"
output_dir="${OPENARM_COMPENSATION_OUTPUT_DIR:-alignment/results/sim_only_compensated_replay_batch_v3}"
mkdir -p "$output_dir"

joints=(
  openarm_left_joint1 openarm_left_joint2 openarm_left_joint3
  openarm_left_joint4 openarm_left_joint5 openarm_left_joint6
  openarm_left_joint7 openarm_right_joint1 openarm_right_joint2
  openarm_right_joint3 openarm_right_joint4 openarm_right_joint6 openarm_right_joint7
)
if [[ "$#" -gt 0 ]]; then
  joints=("$@")
fi

for joint in "${joints[@]}"; do
  echo "COMPENSATED_REPLAY_JOINT=$joint"
  /usr/bin/python3 alignment/measure_sim_only_compensated_replay.py \
    --config "$config" --joint "$joint" --target-rad 0.02 --hold-s 3 \
    --tolerance-rad 0.01 --output "$output_dir/$joint.json"
done

/usr/bin/python3 - "$output_dir" <<'PY'
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
records = [json.loads(path.read_text(encoding="utf-8"))
           for path in sorted(directory.glob("openarm_*_joint*.json"))]
summary = {
    "kind": "openarm_sim_only_compensated_replay_batch",
    "joint_count": len(records),
    "passed_joint_count": sum(record.get("passed", False) for record in records),
    "all_passed": bool(records) and all(record.get("passed", False) for record in records),
    "max_target_error_rad": max(abs(record["target_error_rad"]) for record in records),
    "max_return_error_rad": max(abs(record["return_error_rad"]) for record in records),
    "joints": [{"joint": record["joint"], "passed": record["passed"],
                "target_error_rad": record["target_error_rad"],
                "return_error_rad": record["return_error_rad"]} for record in records],
}
(directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
if not summary["all_passed"]:
    raise SystemExit(2)
PY
