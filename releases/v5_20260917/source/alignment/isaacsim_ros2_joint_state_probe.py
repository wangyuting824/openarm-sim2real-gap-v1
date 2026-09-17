"""Publish a read-only ROS 2 JointState probe from inside Isaac Sim.

This is an end-to-end DDS diagnostic.  It does not subscribe to commands and
does not write to the USD stage.  Stop it by rerunning this script: the prior
publisher/subscription is then destroyed.
"""
from __future__ import annotations

import builtins
import time

import omni.kit.app
import omni.usd
import rclpy
from sensor_msgs.msg import JointState

TOPIC = "/sim/openarm/joint_states_probe"


def main() -> None:
    old = getattr(builtins, "_openarm_ros_probe", None)
    if old is not None:
        old["subscription"] = None
        old["node"].destroy_node()
        print("Stopped previous ROS probe.")

    if not rclpy.ok():
        rclpy.init()
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open.")
    joint_names = [
        prim.GetName()
        for prim in stage.Traverse()
        if prim.GetTypeName() in ("PhysicsRevoluteJoint", "PhysicsPrismaticJoint")
    ]
    node = rclpy.create_node("openarm_isaac_joint_state_probe")
    publisher = node.create_publisher(JointState, TOPIC, 10)
    state = {"node": node, "subscription": None, "last_publish": 0.0, "count": 0}

    def on_update(_event) -> None:
        now = time.monotonic()
        if now - state["last_publish"] < 0.2:
            return
        message = JointState()
        message.header.stamp = node.get_clock().now().to_msg()
        message.name = joint_names
        # Empty position/velocity/effort is intentional: this tests the ROS
        # transport only and makes no claim about articulation state yet.
        publisher.publish(message)
        state["last_publish"] = now
        state["count"] += 1
        if state["count"] == 1:
            print("OPENARM_ROS_PROBE_PUBLISHING topic=" + TOPIC)

    state["subscription"] = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(on_update)
    builtins._openarm_ros_probe = state
    print("OPENARM_ROS_PROBE_ARMED topic=" + TOPIC)
    print("This probe publishes names only and never controls the robot.")


main()
