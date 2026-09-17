#!/usr/bin/env bash
# Fetch a read-only Isaac R J5 diagnostic; it never publishes a robot command.
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
exec /usr/bin/python3 alignment/read_isaacsim_right_j5_diagnostic.py
