#!/usr/bin/env bash
# Fetch the read-only Isaac drive/physics probe and print the fields needed
# before any velocity/control-rate or solver sweep.
set -euo pipefail

host="${1:-tangyuan@192.168.18.72}"
remote="/home/tangyuan/openarm_ws/alignment/results/isaacsim_joint_drive_probe.json"
local="alignment/results/isaacsim_joint_drive_probe_remote.json"
mkdir -p "$(dirname "$local")"
scp "$host:$remote" "$local"
python3 alignment/summarize_isaac_physics_fingerprint.py --input "$local"
echo "OPENARM_ISAAC_PHYSICS_FINGERPRINT_FETCHED=$local"
