#!/usr/bin/env bash
# Isaac-only RTF probe.  It refuses to compete with an existing GUI/Kit process.
set -euo pipefail

default_stage="/home/tangyuan/openarm_ws/alignment/exports/openarm_isaacsim_scene_v1.usda"
stage="${1:-$default_stage}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
isaac_root="${ISAAC_ROOT:-/home/tangyuan/isaacsim}"
if [[ ! -x "$isaac_root/python.sh" ]]; then
  for candidate in /home/tangyuan/isaacsim*/python.sh; do
    [[ -x "$candidate" ]] || continue
    isaac_root="$(dirname "$candidate")"
    break
  done
fi

if [[ ! -x "$isaac_root/python.sh" ]]; then
  echo "REFUSED: Isaac python launcher not found: $isaac_root/python.sh" >&2
  exit 2
fi
if [[ ! -f "$stage" ]]; then
  echo "REFUSED: stage does not exist: $stage" >&2
  echo "First export the currently open stage through /openarm/isaac_gap/export_current_stage." >&2
  exit 2
fi
existing_isaac="$(pgrep -af '/isaacsim[^/]*/kit/kit|/kit/kit .*isaacsim\.' || true)"
if [[ -n "$existing_isaac" ]]; then
  echo "REFUSED: an Isaac/Kit process is already running; stop it or use a clean host before the headless A/B." >&2
  printf '%s\n' "$existing_isaac" >&2
  exit 3
fi

exec env \
  -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  "$isaac_root/python.sh" "$script_dir/isaacsim_headless_realtime_probe.py" \
  --stage "$stage" --alignment-dir "$script_dir"
