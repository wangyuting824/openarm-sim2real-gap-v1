#!/usr/bin/env bash
# Copy Isaac-only compensation replay files to the Isaac host.  This script
# transfers files only; it does not start ROS routers or send robot commands.
set -euo pipefail

host="${1:-tangyuan@192.168.18.72}"
remote_root="/home/tangyuan/openarm_ws/alignment"

ssh "$host" "mkdir -p '$remote_root/calibrations'"
scp \
  alignment/isaacsim_gap_control_daemon.py \
  alignment/isaacsim_timestamped_command_bridge.py \
  alignment/isaacsim_enable_compensation_replay.py \
  alignment/isaacsim_disable_compensation_replay.py \
  "$host:$remote_root/"
scp alignment/calibrations/openarm_isaac_compare_replay_compensation_v1.json \
  alignment/calibrations/openarm_isaac_replay_calibration_v2.json \
  alignment/calibrations/openarm_isaac_replay_calibration_v3.json \
  "$host:$remote_root/calibrations/"

echo "ISAAC_COMPENSATION_REPLAY_FILES_DEPLOYED host=$host"
echo "In Isaac Script Editor, reload isaacsim_gap_control_daemon.py, then call /openarm/isaac_gap/enable_compensation_replay."
