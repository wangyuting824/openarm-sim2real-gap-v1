"""Simulator-only ROS 2 JointState publisher. Run in Isaac Sim Script Editor."""
import builtins
import json
import time
import numpy as np
import omni.kit.app
import omni.timeline
import omni.physx
import rclpy
from sensor_msgs.msg import JointState
from std_msgs.msg import String

ROOT = "/openarm_v20/Geometry/world/openarm_body_link0"
STATE_TOPIC = "/sim/openarm/joint_states_v2"
PUBLISH_HZ = 60.0


def _physics_clock():
    """Return the process-wide elapsed PhysX clock.

    UI timeline time can be stationary even while PhysX step events occur in
    this integration.  State headers therefore use accumulated actual PhysX
    dt, which is the only valid simulation timebase for dynamic analysis.
    """
    clock = getattr(builtins, "_openarm_isaac_physics_clock", None)
    if clock is None:
        clock = {"elapsed_s": 0.0, "step_count": 0, "subscription": None}

        def on_physics_step(dt):
            value = float(dt)
            if value >= 0.0:
                clock["elapsed_s"] += value
                clock["step_count"] += 1

        clock["subscription"] = omni.physx.get_physx_interface().subscribe_physics_step_events(on_physics_step)
        builtins._openarm_isaac_physics_clock = clock
    return clock


def _physics_stamp():
    """Return accumulated actual PhysX time as a ROS Time message."""
    seconds = max(0.0, float(_physics_clock()["elapsed_s"]))
    sec = int(seconds)
    nanosec = int(round((seconds - sec) * 1_000_000_000))
    if nanosec >= 1_000_000_000:
        sec += 1
        nanosec -= 1_000_000_000
    from builtin_interfaces.msg import Time
    return Time(sec=sec, nanosec=nanosec)

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
timing_publisher = node.create_publisher(String, "/openarm/isaac_gap/timing_json", 32)
state = {"node": node, "arm": arm, "sub": None, "initialized": False,
         "last": 0.0, "count": 0, "printed_error": False}
_physics_clock()
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
        msg.header.stamp = _physics_stamp()
        msg.name = list(arm.dof_names)
        msg.position = [float(x) for x in np.asarray(arm.get_joint_positions()).reshape(-1)]
        velocity = np.asarray(arm.get_joint_velocities()).reshape(-1)
        msg.velocity = [float(x) for x in velocity] if len(velocity) == len(msg.name) else []
        publisher.publish(msg)
        timing_records = getattr(builtins, "_openarm_isaac_command_timing", [])
        for record in timing_records:
            if (record.get("first_physics_response_monotonic_s") is not None and
                    record.get("state_published_monotonic_s") is None):
                record["state_published_monotonic_s"] = now
                record["state_published_physics_s"] = (
                    int(msg.header.stamp.sec) + int(msg.header.stamp.nanosec) / 1_000_000_000.0)
                timing = String()
                timing.data = json.dumps(record, separators=(",", ":"))
                timing_publisher.publish(timing)
                print("OPENARM_STATE_PUBLISHED_AFTER_RESPONSE sequence=%d" % record["sequence"])
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
