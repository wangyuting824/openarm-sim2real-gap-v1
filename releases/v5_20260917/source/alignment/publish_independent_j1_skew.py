#!/usr/bin/env python3
"""Publish separately stamped left and right J1 commands for receipt-skew tests."""
import time

import rclpy
from sensor_msgs.msg import JointState

TOPIC = "/sim/openarm/timestamped_joint_command"
COMMANDS = [
    ("left", "openarm_left_joint1", -0.0061804564),
    ("right", "openarm_right_joint1", 0.0071758609),
]
WAIT_TIMEOUT_S = 15.0
INTER_COMMAND_S = 0.0


def main():
    rclpy.init()
    node = rclpy.create_node("openarm_independent_j1_skew_publisher")
    publisher = node.create_publisher(JointState, TOPIC, 10)
    deadline = time.monotonic() + WAIT_TIMEOUT_S
    while publisher.get_subscription_count() < 2:
        if time.monotonic() >= deadline:
            raise RuntimeError("Timed out waiting for bridge and bag recorder")
        rclpy.spin_once(node, timeout_sec=0.1)
    print("MATCHED_SUBSCRIBERS=%d" % publisher.get_subscription_count())
    for label, joint, target in COMMANDS:
        msg = JointState()
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.name, msg.position = [joint], [target]
        publisher.publish(msg)
        print("INDEPENDENT_COMMAND arm=%s stamp=%d.%09d target=%.10f" %
              (label, msg.header.stamp.sec, msg.header.stamp.nanosec, target))
        if INTER_COMMAND_S:
            time.sleep(INTER_COMMAND_S)
    time.sleep(2.0)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
