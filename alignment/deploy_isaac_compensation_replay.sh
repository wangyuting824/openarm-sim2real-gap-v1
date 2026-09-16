#!/usr/bin/env bash
# Copy Isaac-only compensation replay files to the Isaac host.  This script
# transfers files only; it does not start ROS routers or send robot commands.
set -euo pipefail

host="${1:-tangyuan@192.168.18.72}"
remote_root="/home/tangyuan/openarm_ws/alignment"
calibration="alignment/calibrations/openarm_isaac_replay_calibration_v3.json"
local_sha256="$(sha256sum "$calibration" | awk '{print $1}')"

ssh "$host" "mkdir -p '$remote_root/calibrations'"
scp \
  alignment/isaacsim_gap_control_daemon.py \
  alignment/isaacsim_timestamped_command_bridge.py \
  alignment/isaacsim_enable_compensation_replay.py \
  alignment/isaacsim_disable_compensation_replay.py \
  "$host:$remote_root/"
scp alignment/calibrations/openarm_isaac_compare_replay_compensation_v1.json \
  alignment/calibrations/openarm_isaac_replay_calibration_v2.json \
  "$calibration" \
  "$host:$remote_root/calibrations/"

remote_sha256="$(ssh "$host" "sha256sum '$remote_root/calibrations/openarm_isaac_replay_calibration_v3.json' | awk '{print \$1}'")"
if [[ "$local_sha256" != "$remote_sha256" ]]; then
  echo "REFUSED: remote v3 calibration checksum differs local=$local_sha256 remote=$remote_sha256" >&2
  exit 1
fi

echo "ISAAC_COMPENSATION_REPLAY_FILES_DEPLOYED host=$host calibration=v3 sha256=$local_sha256"
echo "In Isaac Script Editor, reload isaacsim_gap_control_daemon.py, then call /openarm/isaac_gap/enable_compensation_replay."
