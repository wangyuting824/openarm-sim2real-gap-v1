#!/usr/bin/env bash
# Start the real OpenArm state/control stack.
# This enables the motors and the current hardware plugin performs return_to_zero
# during activation. Review the robot area and emergency stop before running.
set -eo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
# The Isaac bridge and the real host use domain 42 in this deployment.  Keep
# this default in the launcher so a terminal that forgot its exports cannot
# bring up hardware in domain 0, where paired preflight cannot see it.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
exec ros2 launch openarm_bringup openarm.bimanual.launch.py \
  arm_type:=v2.0 \
  use_fake_hardware:=false \
  fake_sensor_commands:=false \
  robot_controller:=forward_position_controller \
  use_rviz:=false \
  right_can_interface:=can0 \
  left_can_interface:=can1
