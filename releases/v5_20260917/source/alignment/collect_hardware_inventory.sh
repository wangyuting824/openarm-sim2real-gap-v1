#!/usr/bin/env bash
# Read-only hardware/ROS inventory for an Isaac Sim migration session.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_ID="${1:-isaacsim_$(date +%Y%m%d_%H%M%S)}"
SESSION_DIR="$ROOT_DIR/alignment/results/isaacsim_migration/$SESSION_ID"

mkdir -p "$SESSION_DIR"/{control,calibration,objects,workspace,vision,bimanual,contact,trajectories,replay}
source /opt/ros/jazzy/setup.bash
source "$ROOT_DIR/install/setup.bash"

cat > "$SESSION_DIR/metadata.yaml" <<EOF
session_id: "$SESSION_ID"
datetime: "$(date --iso-8601=seconds)"
operator: "填写"
robot: "OpenArm 2.0"
firmware: "填写"
hardware: "填写"
ros_distro: "jazzy"
isaac_sim_version: "填写"
isaac_lab_version: "填写"
source_commit: "$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
notes: "只读硬件身份采集"
EOF

hostnamectl > "$SESSION_DIR/control/host.txt" 2>&1 || true
uname -a >> "$SESSION_DIR/control/host.txt" 2>&1 || true
ip -details link show can0 can1 > "$SESSION_DIR/control/can.txt" 2>&1 || true
lsusb > "$SESSION_DIR/control/usb.txt" 2>&1 || true
ros2 node list > "$SESSION_DIR/control/ros_nodes.txt" 2>&1 || true
ros2 topic list > "$SESSION_DIR/control/ros_topics.txt" 2>&1 || true
ros2 topic list | grep -E 'joint_states|/tf|image|camera_info|command|wrench|force|torque|effort' \
  > "$SESSION_DIR/control/relevant_topics.txt" 2>&1 || true
ros2 topic info /joint_states -v > "$SESSION_DIR/control/joint_states_info.txt" 2>&1 || true
ros2 topic echo /joint_states --once > "$SESSION_DIR/control/joint_states_once.txt" 2>&1 || true

if command -v rs-enumerate-devices >/dev/null 2>&1; then
  rs-enumerate-devices > "$SESSION_DIR/control/realsense_devices.txt" 2>&1 || true
fi
if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl --list-devices > "$SESSION_DIR/control/v4l2_devices.txt" 2>&1 || true
fi

ros2 pkg prefix openarm_bringup openarm_hardware openarm_teleop_ker \
  > "$SESSION_DIR/control/ros_package_prefix.txt" 2>&1 || true
git -C "$ROOT_DIR" log -1 --oneline > "$SESSION_DIR/control/workspace_commit.txt" 2>&1 || true
printf '%s\n' "$SESSION_DIR"
