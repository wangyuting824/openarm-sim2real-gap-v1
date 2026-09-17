#!/usr/bin/env bash
# Restore the reversible live Isaac arm-drive baseline after a stage restart.
# The daemon service edits only the live Isaac session and never enables a
# real route, publishes a robot command, or writes the source USD.
set -eo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS2CLI_DISABLE_DAEMON=1
export ROS_LOG_DIR="${ROS_LOG_DIR:-/tmp/openarm_ros_logs}"
mkdir -p "$ROS_LOG_DIR"

ros2 service call /openarm/isaac_gap/repair_all_arm_drives std_srvs/srv/Trigger '{}'
sleep 2
bash alignment/run_isaacsim_right_j5_readonly_diagnostic.sh
