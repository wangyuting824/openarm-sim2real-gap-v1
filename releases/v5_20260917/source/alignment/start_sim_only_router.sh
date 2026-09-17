#!/usr/bin/env bash
# Start the OpenArm dual-target router in simulator-only mode.
# It may publish only /sim/openarm/timestamped_joint_command; real publish calls
# are disabled by --params enable_real:=false.
set -eo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"

existing="$(pgrep -af '[d]ual_target_command_router' || true)"
if [[ -n "$existing" ]]; then
  echo "Refusing to start a duplicate router:" >&2
  echo "$existing" >&2
  exit 2
fi
exec /usr/bin/python3 alignment/dual_target_command_router.py \
  --ros-args -p enable_real:=false
