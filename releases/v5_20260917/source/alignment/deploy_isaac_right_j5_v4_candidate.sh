#!/usr/bin/env bash
# Transfer the R J5 v4 candidate and its Isaac-only control files.
# Transfer only: no command is published and no real route is started.
set -euo pipefail

host="${1:-tangyuan@192.168.18.72}"
remote_root="/home/tangyuan/openarm_ws/alignment"
calibration="alignment/calibrations/openarm_isaac_replay_calibration_v4_candidate_right_j5.json"
local_sha256="$(sha256sum "$calibration" | awk '{print $1}')"

ssh "$host" "mkdir -p '$remote_root/calibrations'"
scp \
  alignment/isaacsim_gap_control_daemon.py \
  alignment/isaacsim_timestamped_command_bridge.py \
  alignment/isaacsim_enable_right_j5_v4_candidate_replay.py \
  alignment/isaacsim_disable_compensation_replay.py \
  "$host:$remote_root/"
scp "$calibration" "$host:$remote_root/calibrations/"

remote_sha256="$(ssh "$host" "sha256sum '$remote_root/calibrations/$(basename "$calibration")' | awk '{print \$1}'")"
[[ "$local_sha256" == "$remote_sha256" ]] || {
  echo "REFUSED: remote candidate checksum differs local=$local_sha256 remote=$remote_sha256" >&2
  exit 1
}

echo "ISAAC_RIGHT_J5_V4_CANDIDATE_DEPLOYED host=$host sha256=$local_sha256"
echo "Reload isaacsim_gap_control_daemon.py in Isaac, then run:"
echo "  bash alignment/run_isaac_right_j5_v4_candidate_validation.sh"
