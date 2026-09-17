#!/usr/bin/env bash
# Start Isaac Sim 6.x as a WebRTC service, isolated from any ROS 2 environment.
# Usage on the Isaac host:
#   ISAAC_ROOT=$HOME/isaacsim-6.0.1 ISAAC_PUBLIC_IP=192.168.18.72 \
#     bash ~/openarm_ws/alignment/start_isaacsim_streaming.sh
set -euo pipefail

if [[ -z "${ISAAC_ROOT:-}" ]]; then
  for candidate in \
    "$HOME/isaacsim-6.0.1" \
    "$HOME/isaacsim" \
    "$HOME/zitian/software/isaacsim-6.0.1"; do
    if [[ -x "$candidate/isaac-sim.streaming.sh" ]]; then
      ISAAC_ROOT="$candidate"
      break
    fi
  done
fi

: "${ISAAC_ROOT:?Set ISAAC_ROOT to the Isaac Sim installation directory}"
if [[ ! -x "$ISAAC_ROOT/isaac-sim.streaming.sh" ]]; then
  echo "Streaming launcher not found: $ISAAC_ROOT/isaac-sim.streaming.sh" >&2
  exit 1
fi

PUBLIC_IP="${ISAAC_PUBLIC_IP:-$(hostname -I | awk '{print $1}')}"
: "${PUBLIC_IP:?Set ISAAC_PUBLIC_IP to the LAN address of this host}"
SIGNAL_PORT="${ISAAC_SIGNAL_PORT:-49100}"
STREAM_PORT="${ISAAC_STREAM_PORT:-47998}"

cd "$ISAAC_ROOT"
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
  "$ISAAC_ROOT/isaac-sim.streaming.sh" \
  --no-ros-env \
  --/isaac/startup/ros_bridge_extension= \
  --/exts/omni.kit.livestream.app/primaryStream/publicIp="$PUBLIC_IP" \
  --/exts/omni.kit.livestream.app/primaryStream/signalPort="$SIGNAL_PORT" \
  --/exts/omni.kit.livestream.app/primaryStream/streamPort="$STREAM_PORT" \
  "$@"
