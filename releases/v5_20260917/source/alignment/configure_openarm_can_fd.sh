#!/usr/bin/env bash
# Configure the two OpenArm PCAN-USB FD interfaces.  No motor command is sent.
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run with sudo: sudo bash alignment/configure_openarm_can_fd.sh" >&2
  exit 2
fi

if pgrep -af ros2_control_node >/dev/null; then
  echo "REFUSED: ros2_control_node still owns CAN. Stop it before reconfiguring CAN." >&2
  pgrep -af ros2_control_node >&2
  exit 2
fi

if ! command -v openarm-can-cli >/dev/null; then
  echo "ERROR: openarm-can-cli is not installed or not on PATH." >&2
  exit 127
fi

for can_name in can0 can1; do
  if [[ ! -e /sys/class/net/${can_name} ]]; then
    echo "ERROR: ${can_name} does not exist." >&2
    exit 1
  fi
  echo "CONFIGURING ${can_name}: CAN-FD nominal=1M data=5M"
  openarm-can-cli -i "${can_name}" can_configure
done

echo "CAN_CONFIGURATION_COMPLETE"
ip -details -statistics link show can0
ip -details -statistics link show can1
