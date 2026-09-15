"""Simulator-only ROS 2 command bridge with continuous position-target hold."""
import builtins
import numpy as np
import omni.kit.app
import omni.timeline
import rclpy
from rclpy.executors import SingleThreadedExecutor
from sensor_msgs.msg import JointState

ROOT = "/openarm_v20/Geometry/world/openarm_body_link0"
COMMAND_TOPIC = "/sim/openarm/timestamped_joint_command"
RECEIPT_TOPIC = "/sim/openarm/command_receipt"

# The static-baseline helper applies its captured pose every Kit update.  It
# must not remain active when this bridge owns articulation position targets.
static_hold = getattr(builtins, "_openarm_static_hold", None)
if static_hold is not None:
    static_hold["subscription"] = None
    builtins._openarm_static_hold = None
    print("OPENARM_STATIC_HOLD_STOPPED_FOR_COMMAND_BRIDGE")

try:
    from isaacsim.core.prims import Articulation
    arm = Articulation(prim_paths_expr=ROOT, name="openarm_command_bridge")
except (ImportError, TypeError):
    from omni.isaac.core.articulations import Articulation
    arm = Articulation(prim_path=ROOT, name="openarm_command_bridge")

try:
    from isaacsim.core.utils.types import ArticulationActions
except ImportError:
    from omni.isaac.core.utils.types import ArticulationActions

old = getattr(builtins, "_openarm_timestamped_bridge", None)
if old is not None:
    old["sub"] = None
    old["ros_sub"] = None
    try:
        old["executor"].remove_node(old["node"])
        old["node"].destroy_node()
    except Exception:
        pass

if not rclpy.ok():
    rclpy.init()
node = rclpy.create_node("openarm_isaac_timestamped_command_bridge")
executor = SingleThreadedExecutor()
executor.add_node(node)
receipt_pub = node.create_publisher(JointState, RECEIPT_TOPIC, 10)

bridge = {"node": node, "executor": executor, "arm": arm, "sub": None,
          "ros_sub": None, "initialized": False, "name_to_index": {},
          "pending": None, "active_target": None, "sequence": 0,
          "apply_count": 0, "printed_error": False}

def callback(message):
    print("OPENARM_COMMAND_CALLBACK")
    if not bridge["initialized"] or len(message.name) != len(message.position):
        print("OPENARM_COMMAND_REJECTED")
        return
    unknown = [n for n in message.name if n not in bridge["name_to_index"]]
    if unknown:
        print("OPENARM_COMMAND_REJECTED unknown=" + repr(unknown))
        return
    bridge["pending"] = (list(message.name), [float(x) for x in message.position],
                         [bridge["name_to_index"][n] for n in message.name], message.header.stamp)
    print("OPENARM_COMMAND_RECEIVED " + repr(message.name))

bridge["ros_sub"] = node.create_subscription(JointState, COMMAND_TOPIC, callback, 10)
omni.timeline.get_timeline_interface().play()

def on_update(_event):
    try:
        if not bridge["initialized"]:
            arm.initialize()
            bridge["name_to_index"] = {n: i for i, n in enumerate(arm.dof_names)}
            bridge["initialized"] = True
            print("OPENARM_TIMESTAMPED_BRIDGE_READY dofs=%d" % len(arm.dof_names))
        executor.spin_once(timeout_sec=0.0)
        if bridge["pending"] is not None:
            names, positions, indices, source = bridge["pending"]
            bridge["pending"] = None
            bridge["active_target"] = (positions, indices)
            bridge["sequence"] += 1
            bridge["apply_count"] = 0
            receipt = JointState()
            receipt.header.stamp = node.get_clock().now().to_msg()
            receipt.name, receipt.position = names, positions
            receipt.velocity = [float(source.sec), float(source.nanosec)]
            receipt_pub.publish(receipt)
            print("OPENARM_COMMAND_ACCEPTED sequence=%d" % bridge["sequence"])
        if bridge["active_target"] is not None:
            positions, indices = bridge["active_target"]
            action = ArticulationActions(joint_positions=np.asarray(positions, dtype=np.float32).reshape(1, -1),
                                         joint_indices=np.asarray(indices, dtype=np.int64))
            arm.apply_action(action)
            bridge["apply_count"] += 1
            if bridge["apply_count"] == 1:
                print("OPENARM_COMMAND_APPLIED sequence=%d" % bridge["sequence"])
            elif bridge["apply_count"] % 240 == 0:
                print("OPENARM_POSITION_TARGET_HELD sequence=%d applies=%d" % (bridge["sequence"], bridge["apply_count"]))
    except Exception as error:
        if not bridge["printed_error"]:
            print("OPENARM_BRIDGE_ERROR " + repr(error))
            bridge["printed_error"] = True

bridge["sub"] = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(on_update)
builtins._openarm_timestamped_bridge = bridge
print("OPENARM_TIMESTAMPED_BRIDGE_ARMED")
