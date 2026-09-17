#!/usr/bin/env python3
"""Route one named ROS JointState command to Isaac Sim and optionally OpenArm hardware.

Input:  /openarm/command                         sensor_msgs/msg/JointState
Output: /sim/openarm/timestamped_joint_command    sensor_msgs/msg/JointState
        /left_forward_position_controller/commands  std_msgs/msg/Float64MultiArray
        /right_forward_position_controller/commands std_msgs/msg/Float64MultiArray
        /left_gripper_forward_position_controller/commands   std_msgs/msg/Float64MultiArray
        /right_gripper_forward_position_controller/commands  std_msgs/msg/Float64MultiArray

The physical outputs are disabled by default.  When enabled, arm commands are
only sent after a complete real /joint_states sample has seeded every required
joint.  This prevents an incomplete command from becoming a zero-position
command on hardware.
"""

import csv
import json
import time
from pathlib import Path
from typing import Dict

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray, String


LEFT_ARM = [f"openarm_left_joint{i}" for i in range(1, 8)]
RIGHT_ARM = [f"openarm_right_joint{i}" for i in range(1, 8)]
LEFT_GRIPPER = "openarm_left_finger_joint1"
RIGHT_GRIPPER = "openarm_right_finger_joint1"
REAL_REQUIRED = LEFT_ARM + RIGHT_ARM + [LEFT_GRIPPER, RIGHT_GRIPPER]
DEFAULT_LIMITS = Path(__file__).with_name("mechanical_limits.csv")


class DualTargetCommandRouter(Node):
    def __init__(self):
        super().__init__("openarm_dual_target_command_router")
        self.declare_parameter("enable_real", False)
        self.declare_parameter("real_authorization_id", "")
        self.declare_parameter("max_delta_rad", 0.03)
        self.declare_parameter("real_state_max_age_s", 0.25)
        self.declare_parameter("real_publish_hz", 0.0)
        self.declare_parameter("limits_csv", str(DEFAULT_LIMITS))
        self.declare_parameter("command_topic", "/openarm/command")
        self.declare_parameter("real_state_topic", "/joint_states")
        self.declare_parameter(
            "sim_command_topic", "/sim/openarm/timestamped_joint_command"
        )

        requested_real = bool(self.get_parameter("enable_real").value)
        self.real_authorization_id = str(
            self.get_parameter("real_authorization_id").value
        )
        self.enable_real = requested_real and bool(self.real_authorization_id)
        self.max_delta_rad = float(self.get_parameter("max_delta_rad").value)
        self.real_state_max_age_s = float(
            self.get_parameter("real_state_max_age_s").value
        )
        self.real_publish_hz = float(self.get_parameter("real_publish_hz").value)
        if self.real_publish_hz < 0.0:
            raise RuntimeError("real_publish_hz must be non-negative")
        limits_path = Path(str(self.get_parameter("limits_csv").value))
        self.limits = self.load_limits(limits_path)
        command_topic = str(self.get_parameter("command_topic").value)
        state_topic = str(self.get_parameter("real_state_topic").value)
        sim_topic = str(self.get_parameter("sim_command_topic").value)
        self.real_position: Dict[str, float] = {}
        self.last_real_state_monotonic = None
        self.sequence = 0
        self.active_real_target = None
        self.stream_blocked_reason = None

        self.sim_pub = self.create_publisher(JointState, sim_topic, 10)
        self.left_pub = self.create_publisher(
            Float64MultiArray, "/left_forward_position_controller/commands", 10
        )
        self.right_pub = self.create_publisher(
            Float64MultiArray, "/right_forward_position_controller/commands", 10
        )
        self.left_gripper_pub = self.create_publisher(
            Float64MultiArray,
            "/left_gripper_forward_position_controller/commands",
            10,
        )
        self.right_gripper_pub = self.create_publisher(
            Float64MultiArray,
            "/right_gripper_forward_position_controller/commands",
            10,
        )
        self.receipt_pub = self.create_publisher(
            String, "/openarm/dual_command_receipt", 10
        )
        self.create_subscription(JointState, state_topic, self.on_real_state, 20)
        self.create_subscription(JointState, command_topic, self.on_command, 20)
        self.real_stream_timer = None
        if self.enable_real and self.real_publish_hz > 0.0:
            self.real_stream_timer = self.create_timer(
                1.0 / self.real_publish_hz, self.stream_real_target
            )

        self.get_logger().info(
            "router ready: input=%s sim=%s enable_real=%s authorization=%s real_publish_hz=%s"
            % (command_topic, sim_topic, self.enable_real,
               bool(self.real_authorization_id), self.real_publish_hz)
        )
        if requested_real and not self.enable_real:
            self.get_logger().error(
                "Real routing requested but blocked: real_authorization_id is empty"
            )

    @staticmethod
    def load_limits(path: Path) -> Dict[str, tuple]:
        limits = {}
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                limits[row["joint"]] = (float(row["lower_rad"]), float(row["upper_rad"]))
        missing = [joint for joint in REAL_REQUIRED if joint not in limits]
        if missing:
            raise RuntimeError("mechanical limits missing for " + repr(missing))
        return limits

    def on_real_state(self, message: JointState) -> None:
        for name, position in zip(message.name, message.position):
            if name in REAL_REQUIRED:
                self.real_position[name] = float(position)
        self.last_real_state_monotonic = time.monotonic()

    def emit_receipt(self, accepted: bool, reason: str, sim_sent: bool, real_sent: bool):
        self.sequence += 1
        message = String()
        message.data = json.dumps({
            "sequence": self.sequence,
            "accepted": accepted,
            "reason": reason,
            "sim_sent": sim_sent,
            "real_sent": real_sent,
            "real_feedback_seeded": all(joint in self.real_position for joint in REAL_REQUIRED),
            "real_authorization_present": bool(self.real_authorization_id),
        }, separators=(",", ":"))
        self.receipt_pub.publish(message)

    def on_command(self, message: JointState) -> None:
        if len(message.name) != len(message.position):
            self.emit_receipt(False, "name_position_length_mismatch", False, False)
            self.get_logger().error("Rejected command: name and position length differ")
            return

        command = dict(zip(message.name, message.position))
        if not command:
            self.emit_receipt(False, "empty_command", False, False)
            return

        unknown = sorted(set(command) - set(REAL_REQUIRED))
        if unknown:
            self.emit_receipt(False, "unknown_canonical_joint:" + ",".join(unknown), False, False)
            return

        if self.enable_real:
            rejection = self.real_safety_rejection(command)
            if rejection:
                self.emit_receipt(False, rejection, False, False)
                self.get_logger().error("Rejected real+sim command: " + rejection)
                return

        # Isaac accepts named partial commands. Preserve the original timestamp;
        # give an unstamped command the router's current ROS time.
        sim_command = JointState()
        sim_command.header = message.header
        if sim_command.header.stamp.sec == 0 and sim_command.header.stamp.nanosec == 0:
            sim_command.header.stamp = self.get_clock().now().to_msg()
        sim_command.name = list(message.name)
        sim_command.position = [float(value) for value in message.position]
        self.sim_pub.publish(sim_command)

        if not self.enable_real:
            self.emit_receipt(True, "sim_only_real_disabled", True, False)
            return

        missing_feedback = [
            joint for joint in REAL_REQUIRED if joint not in self.real_position
        ]
        if missing_feedback:
            self.emit_receipt(False, "real_feedback_not_seeded", True, False)
            self.get_logger().error(
                "Isaac received command; real command blocked until /joint_states contains: %s"
                % missing_feedback
            )
            return

        target = dict(self.real_position)
        for name, position in command.items():
            if name in target:
                target[name] = float(position)

        self.publish_real_target(target, command)
        self.active_real_target = target
        self.stream_blocked_reason = None

        self.emit_receipt(True, "sim_and_real_sent", True, True)

    def publish_real_target(self, target, command=None):
        self.left_pub.publish(Float64MultiArray(data=[target[name] for name in LEFT_ARM]))
        self.right_pub.publish(Float64MultiArray(data=[target[name] for name in RIGHT_ARM]))
        if command is not None and LEFT_GRIPPER in command:
            self.left_gripper_pub.publish(
                Float64MultiArray(data=[target[LEFT_GRIPPER]])
            )
        if command is not None and RIGHT_GRIPPER in command:
            self.right_gripper_pub.publish(
                Float64MultiArray(data=[target[RIGHT_GRIPPER]])
            )

    def stream_real_target(self):
        if self.active_real_target is None:
            return
        if self.last_real_state_monotonic is None or (
            time.monotonic() - self.last_real_state_monotonic > self.real_state_max_age_s
        ):
            self.stream_blocked_reason = "real_feedback_stale"
            self.active_real_target = None
            self.emit_receipt(False, "real_stream_stopped_feedback_stale", False, False)
            self.get_logger().error("Stopped real command stream: feedback stale")
            return
        self.publish_real_target(self.active_real_target)

    def real_safety_rejection(self, command: Dict[str, float]):
        missing_feedback = [joint for joint in REAL_REQUIRED if joint not in self.real_position]
        if missing_feedback:
            return "real_feedback_not_seeded:" + ",".join(missing_feedback)
        if self.last_real_state_monotonic is None or (
            time.monotonic() - self.last_real_state_monotonic > self.real_state_max_age_s
        ):
            return "real_feedback_stale"
        for name, target in command.items():
            lower, upper = self.limits[name]
            if not lower <= float(target) <= upper:
                return "target_out_of_limits:" + name
            if abs(float(target) - self.real_position[name]) > self.max_delta_rad:
                return "target_delta_exceeds_limit:" + name
        for topic in (
            "/left_forward_position_controller/commands",
            "/right_forward_position_controller/commands",
            "/left_gripper_forward_position_controller/commands",
            "/right_gripper_forward_position_controller/commands",
        ):
            if len(self.get_publishers_info_by_topic(topic)) > 1:
                return "multiple_command_publishers:" + topic
        return None


def main():
    rclpy.init()
    node = DualTargetCommandRouter()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        # SIGTERM may already have shut down the default context.  Calling
        # rclpy.shutdown() a second time raises and can leave a parent trial
        # runner waiting on a router that should have exited after return.
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
