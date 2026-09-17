#!/usr/bin/env bash
# Start Isaac Sim Streaming with the isolated OpenArm ROS 2 / Fast DDS setup.
# Does not start real-robot ROS, CAN, or any hardware bridge.
set -euo pipefail

IS6="${IS6:-$HOME/isaacsim-6.0.1}"
WORKSPACE="${WORKSPACE:-$HOME/openarm_ws}"
DDS="${DDS:-$WORKSPACE/alignment/fastdds_udp.xml}"
LOGDIR="${LOGDIR:-$HOME/isaacsim-streaming-logs}"
SERVER_IP="${SERVER_IP:-192.168.18.72}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

test -x "$IS6/isaac-sim.streaming.sh" || {
  echo "Missing Isaac Sim launcher: $IS6/isaac-sim.streaming.sh" >&2
  exit 1
}
test -f "$DDS" || {
  echo "Missing Fast DDS UDP profile: $DDS" >&2
  exit 1
}

mkdir -p "$LOGDIR"
export ROS_DOMAIN_ID
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE="$DDS"

echo "ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
echo "FASTRTPS_DEFAULT_PROFILES_FILE=$FASTRTPS_DEFAULT_PROFILES_FILE"
echo "Streaming server IP=$SERVER_IP"

exec "$IS6/isaac-sim.streaming.sh" \
  --enable isaacsim.ros2.bridge \
  --/exts/omni.kit.livestream.app/primaryStream/publicIp="$SERVER_IP" \
  --/exts/omni.kit.livestream.app/primaryStream/signalPort=49100 \
  --/exts/omni.kit.livestream.app/primaryStream/streamPort=47998
