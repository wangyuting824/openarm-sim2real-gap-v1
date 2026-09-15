"""Simulator-only ROS 2 JointState publisher. Run in Isaac Sim Script Editor."""
import builtins
import time
import numpy as np
import omni.kit.app
import omni.timeline
import rclpy
from sensor_msgs.msg import JointState

ROOT = "/openarm_v20/Geometry/world/openarm_body_link0"
STATE_TOPIC = "/sim/openarm/joint_states_v2"
PUBLISH_HZ = 60.0

try:
    from isaacsim.core.prims import Articulation
    arm = Articulation(prim_paths_expr=ROOT, name="openarm_state_publisher")
except (ImportError, TypeError):
    from omni.isaac.core.articulations import Articulation
    arm = Articulation(prim_path=ROOT, name="openarm_state_publisher")

old = getattr(builtins, "_openarm_state_publisher", None)
if old is not None:
    old["sub"] = None
    try:
        old["node"].destroy_node()
    except Exception:
        pass

if not rclpy.ok():
    rclpy.init()
node = rclpy.create_node("openarm_isaac_joint_state_publisher")
publisher = node.create_publisher(JointState, STATE_TOPIC, 10)
state = {"node": node, "arm": arm, "sub": None, "initialized": False,
         "last": 0.0, "count": 0, "printed_error": False}
omni.timeline.get_timeline_interface().play()

def on_update(_event):
    try:
        if not state["initialized"]:
            arm.initialize()
            state["initialized"] = True
            print("OPENARM_STATE_PUBLISHER_READY dofs=%d" % len(arm.dof_names))
        now = time.monotonic()
        if now - state["last"] < 1.0 / PUBLISH_HZ:
            return
        msg = JointState()
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.name = list(arm.dof_names)
        msg.position = [float(x) for x in np.asarray(arm.get_joint_positions()).reshape(-1)]
        velocity = np.asarray(arm.get_joint_velocities()).reshape(-1)
        msg.velocity = [float(x) for x in velocity] if len(velocity) == len(msg.name) else []
        publisher.publish(msg)
        state["last"] = now
        state["count"] += 1
        if state["count"] == 1:
            print("OPENARM_STATE_PUBLISHED")
    except Exception as error:
        if not state["printed_error"]:
            print("OPENARM_STATE_PUBLISHER_ERROR " + repr(error))
            state["printed_error"] = True

state["sub"] = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(on_update)
builtins._openarm_state_publisher = state
print("OPENARM_STATE_PUBLISHER_ARMED")
