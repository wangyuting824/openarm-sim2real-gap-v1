"""Publish one small simulator-only bimanual JointState command.

Run inside the ROS Jazzy Docker container after the Isaac bridge reports READY.
The two command positions are absolute targets, derived from the validated
stable hold pose with ±0.02 rad change on J1 only.
"""
import rclpy
from sensor_msgs.msg import JointState

TOPIC = "/sim/openarm/timestamped_joint_command"

rclpy.init()
node = rclpy.create_node("openarm_timestamped_bimanual_test_publisher")
publisher = node.create_publisher(JointState, TOPIC, 10)
message = JointState()
message.header.stamp = node.get_clock().now().to_msg()
message.name = ["openarm_left_joint1", "openarm_right_joint1"]
message.position = [-0.03285445224493742, 0.03313929073512554]
publisher.publish(message)
print("OPENARM_TEST_COMMAND_SENT")
print("stamp=%d.%09d" % (message.header.stamp.sec, message.header.stamp.nanosec))
print("topic=" + TOPIC)
rclpy.spin_once(node, timeout_sec=0.2)
node.destroy_node()
rclpy.shutdown()
