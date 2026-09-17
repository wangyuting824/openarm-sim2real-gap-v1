#!/usr/bin/env bash
# Copy only Isaac-only dynamic-diagnosis files.  It never starts a router or
# touches real hardware.
set -euo pipefail

host="${1:-tangyuan@192.168.18.72}"
remote_root="/home/tangyuan/openarm_ws/alignment"
files=(
  alignment/isaacsim_gap_control_daemon.py
  alignment/isaacsim_timestamped_command_bridge.py
  alignment/isaacsim_publish_openarm_joint_state.py
  alignment/isaacsim_inspect_joint_drive.py
  alignment/isaacsim_measure_realtime_factor.py
  alignment/isaacsim_apply_runtime_performance_candidate.py
  alignment/isaacsim_restore_runtime_performance_candidate.py
  alignment/select_isaac_runtime_performance_candidate.py
  alignment/isaacsim_disable_viewport_updates.py
  alignment/isaacsim_restore_viewport_updates.py
  alignment/isaacsim_play_timeline.py
  alignment/isaacsim_headless_realtime_probe.py
  alignment/run_isaacsim_headless_realtime_probe.sh
  alignment/isaacsim_apply_right_j7_dynamic_drive_candidate.py
  alignment/isaacsim_restore_right_j7_dynamic_drive_candidate.py
  alignment/select_right_j7_dynamic_drive_candidate.py
  alignment/select_isaac_physics_rate_candidate.py
  alignment/isaacsim_apply_physics_rate_candidate.py
  alignment/isaacsim_restore_physics_rate_candidate.py
)
configs=(
  alignment/calibrations/openarm_right_j7_dynamic_drive_active_v1.json
  alignment/calibrations/openarm_right_j7_dynamic_drive_sweep_v1.json
  alignment/calibrations/openarm_isaac_physics_rate_sweep_v1.json
  alignment/calibrations/openarm_isaac_physics_rate_active_v1.json
  alignment/calibrations/openarm_isaac_runtime_performance_sweep_v1.json
  alignment/calibrations/openarm_isaac_runtime_performance_active_v1.json
)

ssh "$host" "mkdir -p '$remote_root/calibrations'"
scp "${files[@]}" "$host:$remote_root/"
scp "${configs[@]}" "$host:$remote_root/calibrations/"

local_hash="$(sha256sum "${files[@]}" "${configs[@]}" | awk '{print $1}' | sha256sum | awk '{print $1}')"
remote_hash="$(ssh "$host" "cd '$remote_root' && sha256sum isaacsim_gap_control_daemon.py isaacsim_timestamped_command_bridge.py isaacsim_publish_openarm_joint_state.py isaacsim_inspect_joint_drive.py isaacsim_measure_realtime_factor.py isaacsim_apply_runtime_performance_candidate.py isaacsim_restore_runtime_performance_candidate.py select_isaac_runtime_performance_candidate.py isaacsim_disable_viewport_updates.py isaacsim_restore_viewport_updates.py isaacsim_play_timeline.py isaacsim_headless_realtime_probe.py run_isaacsim_headless_realtime_probe.sh isaacsim_apply_right_j7_dynamic_drive_candidate.py isaacsim_restore_right_j7_dynamic_drive_candidate.py select_right_j7_dynamic_drive_candidate.py select_isaac_physics_rate_candidate.py isaacsim_apply_physics_rate_candidate.py isaacsim_restore_physics_rate_candidate.py calibrations/openarm_right_j7_dynamic_drive_active_v1.json calibrations/openarm_right_j7_dynamic_drive_sweep_v1.json calibrations/openarm_isaac_physics_rate_sweep_v1.json calibrations/openarm_isaac_physics_rate_active_v1.json calibrations/openarm_isaac_runtime_performance_sweep_v1.json calibrations/openarm_isaac_runtime_performance_active_v1.json | awk '{print \$1}' | sha256sum | awk '{print \$1}'")"
if [[ "$local_hash" != "$remote_hash" ]]; then
  echo "REFUSED: dynamic-tool checksum differs local=$local_hash remote=$remote_hash" >&2
  exit 1
fi
echo "ISAAC_J7_DYNAMIC_TOOLS_DEPLOYED sha256=$local_hash"
echo "Reload isaacsim_gap_control_daemon.py in Script Editor, then use apply_right_j7_dynamic_drive."
