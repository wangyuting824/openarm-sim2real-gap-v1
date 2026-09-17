#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${ISAAC_ROOT:-}" ]]; then
  for candidate in \
    "$HOME/isaacsim-6.0.1" \
    "$HOME/isaacsim" \
    "$HOME/zitian/software/isaacsim-6.0.1"; do
    if [[ -x "$candidate/isaac-sim.sh" ]]; then
      ISAAC_ROOT="$candidate"
      break
    fi
  done
fi

: "${ISAAC_ROOT:?Set ISAAC_ROOT to the Isaac Sim installation directory}"
if [[ ! -x "$ISAAC_ROOT/isaac-sim.sh" ]]; then
  echo "Isaac Sim launcher not found: $ISAAC_ROOT/isaac-sim.sh" >&2
  exit 1
fi

cd "$ISAAC_ROOT"

# Do not let a sourced ROS environment or a conda PYTHONPATH override Isaac's
# bundled Python and shared libraries.
exec env \
  -u PYTHONPATH \
  -u PYTHONHOME \
  -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH \
  -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO \
  -u ROS_VERSION \
  -u ROS_PYTHON_VERSION \
  -u RMW_IMPLEMENTATION \
  -u ROS_AUTOMATIC_DISCOVERY_RANGE \
  "$ISAAC_ROOT/isaac-sim.sh" \
  --no-ros-env \
  "$@"
