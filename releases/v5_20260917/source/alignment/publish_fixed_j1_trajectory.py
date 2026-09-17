#!/usr/bin/env python3
"""Publish a deterministic three-phase bimanual J1 trajectory in ROS 2.

Run inside the ROS Jazzy container.  Each message is time-stamped immediately
before publishing, so command-to-receipt latency excludes CLI startup time.
"""

import time

import rclpy
from sensor_msgs.msg import JointState

TOPIC = "/sim/openarm/timestamped_joint_command"
JOINT_NAMES = ["openarm_left_joint1", "openarm_right_joint1"]
PHASES = [
    ("A", [-0.0261804564, 0.0271758609]),
    ("B", [-0.0061804564, 0.0071758609]),
    ("A", [-0.0261804564, 0.0271758609]),
]
PHASE_DURATION_S = 4.0
WAIT_TIMEOUT_S = 15.0


def main():
    rclpy.init()
    node = rclpy.create_node("openarm_fixed_j1_trajectory_publisher")
    publisher = node.create_publisher(JointState, TOPIC, 10)
    deadline = time.monotonic() + WAIT_TIMEOUT_S
    while publisher.get_subscription_count() < 2:
        if time.monotonic() >= deadline:
            raise RuntimeError("Timed out waiting for bridge and bag recorder subscribers")
        rclpy.spin_once(node, timeout_sec=0.1)
        time.sleep(0.1)

    print("MATCHED_SUBSCRIBERS=%d" % publisher.get_subscription_count())
    for label, target in PHASES:
        message = JointState()
        message.header.stamp = node.get_clock().now().to_msg()
        message.name = list(JOINT_NAMES)
        message.position = list(target)
        publisher.publish(message)
        print(
            "PHASE=%s stamp=%d.%09d target=%s"
            % (label, message.header.stamp.sec, message.header.stamp.nanosec, target)
        )
        rclpy.spin_once(node, timeout_sec=0.05)
        time.sleep(PHASE_DURATION_S)

    print("FIXED_TRAJECTORY_COMPLETE")
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
