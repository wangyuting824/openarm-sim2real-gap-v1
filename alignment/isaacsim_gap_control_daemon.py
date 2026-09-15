"""Isaac Sim-side control plane for the OpenArm Sim2Real integration.

Run this once in Isaac Sim Script Editor.  It exposes standard ROS Trigger
services that an external agent can call to load or reload the state publisher
and timestamped command bridge.  It never publishes a robot command itself.
"""
import builtins
import os
import json
from pathlib import Path

import omni.kit.app
import rclpy
from rclpy.executors import SingleThreadedExecutor
from std_srvs.srv import Trigger
from std_msgs.msg import String
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


ALIGNMENT_DIR = Path("/home/tangyuan/openarm_ws/alignment")
STATE_SCRIPT = ALIGNMENT_DIR / "isaacsim_publish_openarm_joint_state.py"
BRIDGE_SCRIPT = ALIGNMENT_DIR / "isaacsim_timestamped_command_bridge.py"
DIAGNOSTIC_SCRIPT = ALIGNMENT_DIR / "isaacsim_inspect_joint_drive.py"
REPAIR_J7_SCRIPT = ALIGNMENT_DIR / "isaacsim_enable_right_j7_position_drive.py"
RESTORE_J7_SCRIPT = ALIGNMENT_DIR / "isaacsim_restore_right_j7_drive.py"
REPAIR_ALL_ARMS_SCRIPT = ALIGNMENT_DIR / "isaacsim_enable_all_arm_position_drives.py"
RESTORE_ALL_ARMS_SCRIPT = ALIGNMENT_DIR / "isaacsim_restore_all_arm_drives.py"


def _stop_old_daemon():
    old = getattr(builtins, "_openarm_gap_control_daemon", None)
    if old is None:
        return
    old["sub"] = None
    try:
        old["executor"].remove_node(old["node"])
        old["node"].destroy_node()
    except Exception:
        pass


def _load_script(path: Path):
    if not path.is_file():
        raise FileNotFoundError(str(path))
    namespace = {"__file__": str(path), "__name__": "__main__"}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)


_stop_old_daemon()
if not rclpy.ok():
    rclpy.init()
node = rclpy.create_node("openarm_isaac_gap_control_daemon")
executor = SingleThreadedExecutor()
executor.add_node(node)
status_qos = QoSProfile(depth=1)
status_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
status_qos.reliability = ReliabilityPolicy.RELIABLE
event_pub = node.create_publisher(String, "/openarm/isaac_gap/events", status_qos)
diagnostic_pub = node.create_publisher(
    String, "/openarm/isaac_gap/diagnostic_json", status_qos
)
daemon = {"node": node, "executor": executor, "sub": None, "pending": [], "errors": [],
          "event_pub": event_pub, "diagnostic_pub": diagnostic_pub, "last_event": "armed"}


def _event(message: str):
    daemon["last_event"] = message
    event = String()
    event.data = message
    daemon["event_pub"].publish(event)
    print("OPENARM_GAP_EVENT " + message)


def _queue(script: Path, label: str, response):
    daemon["pending"].append((script, label))
    _event("queued=" + label)
    response.success = True
    response.message = "queued " + label
    return response


def ensure_state(_request, response):
    return _queue(STATE_SCRIPT, "state_publisher", response)


def ensure_bridge(_request, response):
    return _queue(BRIDGE_SCRIPT, "timestamped_command_bridge", response)


def ensure_diagnose(_request, response):
    return _queue(DIAGNOSTIC_SCRIPT, "joint_drive_diagnostic", response)


def repair_right_j7_drive(_request, response):
    return _queue(REPAIR_J7_SCRIPT, "repair_right_j7_position_drive", response)


def restore_right_j7_drive(_request, response):
    return _queue(RESTORE_J7_SCRIPT, "restore_right_j7_drive", response)


def repair_all_arm_drives(_request, response):
    return _queue(REPAIR_ALL_ARMS_SCRIPT, "repair_all_arm_position_drives", response)


def restore_all_arm_drives(_request, response):
    return _queue(RESTORE_ALL_ARMS_SCRIPT, "restore_all_arm_drives", response)


def ensure_all(_request, response):
    daemon["pending"].extend([
        (STATE_SCRIPT, "state_publisher"),
        (BRIDGE_SCRIPT, "timestamped_command_bridge"),
    ])
    response.success = True
    response.message = "queued state_publisher and timestamped_command_bridge"
    return response


def status(_request, response):
    state = getattr(builtins, "_openarm_state_publisher", None)
    bridge = getattr(builtins, "_openarm_timestamped_bridge", None)
    response.success = state is not None and bridge is not None and not daemon["errors"]
    response.message = (
        "state=%s bridge=%s pending=%d errors=%s last_event=%s"
        % (state is not None, bridge is not None, len(daemon["pending"]), daemon["errors"][-1:] or "none", daemon["last_event"])
    )
    return response


node.create_service(Trigger, "/openarm/isaac_gap/ensure_state", ensure_state)
node.create_service(Trigger, "/openarm/isaac_gap/ensure_bridge", ensure_bridge)
node.create_service(Trigger, "/openarm/isaac_gap/ensure_all", ensure_all)
node.create_service(Trigger, "/openarm/isaac_gap/diagnose", ensure_diagnose)
node.create_service(Trigger, "/openarm/isaac_gap/status", status)
node.create_service(Trigger, "/openarm/isaac_gap/repair_right_j7_drive", repair_right_j7_drive)
node.create_service(Trigger, "/openarm/isaac_gap/restore_right_j7_drive", restore_right_j7_drive)
node.create_service(Trigger, "/openarm/isaac_gap/repair_all_arm_drives", repair_all_arm_drives)
node.create_service(Trigger, "/openarm/isaac_gap/restore_all_arm_drives", restore_all_arm_drives)


def on_update(_kit_event):
    executor.spin_once(timeout_sec=0.0)
    while daemon["pending"]:
        script, label = daemon["pending"].pop(0)
        try:
            _load_script(script)
            message = "loaded=" + label
            if label == "joint_drive_diagnostic":
                probe = ALIGNMENT_DIR / "results" / "isaacsim_joint_drive_probe.json"
                if probe.is_file():
                    data = json.loads(probe.read_text(encoding="utf-8"))
                    diagnostic = String()
                    diagnostic.data = json.dumps(data, separators=(",", ":"))
                    daemon["diagnostic_pub"].publish(diagnostic)
                    message += " drives=%d bridge=%s static_hold=%s diagnostic_topic=/openarm/isaac_gap/diagnostic_json" % (
                        len(data.get("angular_drives", [])),
                        data.get("bridge", {}).get("available"),
                        data.get("static_hold_present"),
                    )
            _event(message)
            if label in ("repair_right_j7_position_drive", "repair_all_arm_position_drives"):
                daemon["pending"].append((BRIDGE_SCRIPT, "timestamped_command_bridge"))
        except Exception as error:
            daemon["errors"].append("%s: %r" % (label, error))
            _event("error=" + daemon["errors"][-1])


daemon["sub"] = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(on_update)
builtins._openarm_gap_control_daemon = daemon
daemon["pending"].extend([
    (STATE_SCRIPT, "state_publisher"),
    (BRIDGE_SCRIPT, "timestamped_command_bridge"),
])
_event("armed domain=%s rmw=%s" % (os.environ.get("ROS_DOMAIN_ID", "0"), os.environ.get("RMW_IMPLEMENTATION", "default")))
print("OPENARM_GAP_DAEMON_ARMED services=/openarm/isaac_gap/{ensure_state,ensure_bridge,ensure_all,diagnose,repair_right_j7_drive,restore_right_j7_drive,repair_all_arm_drives,restore_all_arm_drives,status} topics=/openarm/isaac_gap/{events,diagnostic_json} domain=%s rmw=%s state_script=%s bridge_script=%s" % (os.environ.get("ROS_DOMAIN_ID", "0"), os.environ.get("RMW_IMPLEMENTATION", "default"), STATE_SCRIPT, BRIDGE_SCRIPT))
