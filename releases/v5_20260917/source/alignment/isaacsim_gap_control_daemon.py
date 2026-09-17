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
EXPORT_STAGE_SCRIPT = ALIGNMENT_DIR / "isaacsim_export_current_stage.py"
ENABLE_COMPENSATION_SCRIPT = ALIGNMENT_DIR / "isaacsim_enable_compensation_replay.py"
ENABLE_RIGHT_J5_V4_CANDIDATE_SCRIPT = (
    ALIGNMENT_DIR / "isaacsim_enable_right_j5_v4_candidate_replay.py"
)
DISABLE_COMPENSATION_SCRIPT = ALIGNMENT_DIR / "isaacsim_disable_compensation_replay.py"
APPLY_J7_DYNAMIC_DRIVE_SCRIPT = ALIGNMENT_DIR / "isaacsim_apply_right_j7_dynamic_drive_candidate.py"
RESTORE_J7_DYNAMIC_DRIVE_SCRIPT = ALIGNMENT_DIR / "isaacsim_restore_right_j7_dynamic_drive_candidate.py"
APPLY_PHYSICS_RATE_SCRIPT = ALIGNMENT_DIR / "isaacsim_apply_physics_rate_candidate.py"
RESTORE_PHYSICS_RATE_SCRIPT = ALIGNMENT_DIR / "isaacsim_restore_physics_rate_candidate.py"
REALTIME_FACTOR_SCRIPT = ALIGNMENT_DIR / "isaacsim_measure_realtime_factor.py"
APPLY_RUNTIME_PERFORMANCE_SCRIPT = ALIGNMENT_DIR / "isaacsim_apply_runtime_performance_candidate.py"
RESTORE_RUNTIME_PERFORMANCE_SCRIPT = ALIGNMENT_DIR / "isaacsim_restore_runtime_performance_candidate.py"
DISABLE_VIEWPORT_UPDATES_SCRIPT = ALIGNMENT_DIR / "isaacsim_disable_viewport_updates.py"
RESTORE_VIEWPORT_UPDATES_SCRIPT = ALIGNMENT_DIR / "isaacsim_restore_viewport_updates.py"
PLAY_TIMELINE_SCRIPT = ALIGNMENT_DIR / "isaacsim_play_timeline.py"


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


def export_current_stage(_request, response):
    return _queue(EXPORT_STAGE_SCRIPT, "export_current_stage", response)


def enable_compensation_replay(_request, response):
    daemon["pending"].extend([
        (ENABLE_COMPENSATION_SCRIPT, "enable_compensation_replay"),
        (BRIDGE_SCRIPT, "timestamped_command_bridge"),
    ])
    _event("queued=enable_compensation_replay")
    response.success = True
    response.message = "queued enable_compensation_replay and timestamped_command_bridge"
    return response


def enable_right_j5_v4_candidate_replay(_request, response):
    """Arm a simulator-only candidate and reload only the Isaac bridge."""
    daemon["pending"].extend([
        (ENABLE_RIGHT_J5_V4_CANDIDATE_SCRIPT, "enable_right_j5_v4_candidate_replay"),
        (BRIDGE_SCRIPT, "timestamped_command_bridge"),
    ])
    _event("queued=enable_right_j5_v4_candidate_replay")
    response.success = True
    response.message = (
        "queued enable_right_j5_v4_candidate_replay and "
        "timestamped_command_bridge (Isaac-only)"
    )
    return response


def disable_compensation_replay(_request, response):
    daemon["pending"].extend([
        (DISABLE_COMPENSATION_SCRIPT, "disable_compensation_replay"),
        (BRIDGE_SCRIPT, "timestamped_command_bridge"),
    ])
    _event("queued=disable_compensation_replay")
    response.success = True
    response.message = "queued disable_compensation_replay and timestamped_command_bridge"
    return response


def apply_right_j7_dynamic_drive(_request, response):
    return _queue(APPLY_J7_DYNAMIC_DRIVE_SCRIPT, "apply_right_j7_dynamic_drive", response)


def restore_right_j7_dynamic_drive(_request, response):
    return _queue(RESTORE_J7_DYNAMIC_DRIVE_SCRIPT, "restore_right_j7_dynamic_drive", response)


def apply_physics_rate(_request, response):
    return _queue(APPLY_PHYSICS_RATE_SCRIPT, "apply_physics_rate", response)


def restore_physics_rate(_request, response):
    return _queue(RESTORE_PHYSICS_RATE_SCRIPT, "restore_physics_rate", response)


def measure_realtime_factor(_request, response):
    return _queue(REALTIME_FACTOR_SCRIPT, "measure_realtime_factor", response)


def apply_runtime_performance(_request, response):
    return _queue(APPLY_RUNTIME_PERFORMANCE_SCRIPT, "apply_runtime_performance", response)


def restore_runtime_performance(_request, response):
    return _queue(RESTORE_RUNTIME_PERFORMANCE_SCRIPT, "restore_runtime_performance", response)


def disable_viewport_updates(_request, response):
    return _queue(DISABLE_VIEWPORT_UPDATES_SCRIPT, "disable_viewport_updates", response)


def restore_viewport_updates(_request, response):
    return _queue(RESTORE_VIEWPORT_UPDATES_SCRIPT, "restore_viewport_updates", response)


def play_timeline(_request, response):
    return _queue(PLAY_TIMELINE_SCRIPT, "play_timeline", response)


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
    compensation = bool(getattr(builtins, "_openarm_isaac_compensation_replay", False))
    response.success = state is not None and bridge is not None and not daemon["errors"]
    response.message = (
        "state=%s bridge=%s compensation_replay=%s pending=%d errors=%s last_event=%s"
        % (state is not None, bridge is not None, compensation, len(daemon["pending"]), daemon["errors"][-1:] or "none", daemon["last_event"])
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
node.create_service(Trigger, "/openarm/isaac_gap/export_current_stage", export_current_stage)
node.create_service(Trigger, "/openarm/isaac_gap/enable_compensation_replay", enable_compensation_replay)
node.create_service(
    Trigger,
    "/openarm/isaac_gap/enable_right_j5_v4_candidate_replay",
    enable_right_j5_v4_candidate_replay,
)
node.create_service(Trigger, "/openarm/isaac_gap/disable_compensation_replay", disable_compensation_replay)
node.create_service(Trigger, "/openarm/isaac_gap/apply_right_j7_dynamic_drive", apply_right_j7_dynamic_drive)
node.create_service(Trigger, "/openarm/isaac_gap/restore_right_j7_dynamic_drive", restore_right_j7_dynamic_drive)
node.create_service(Trigger, "/openarm/isaac_gap/apply_physics_rate", apply_physics_rate)
node.create_service(Trigger, "/openarm/isaac_gap/restore_physics_rate", restore_physics_rate)
node.create_service(Trigger, "/openarm/isaac_gap/measure_realtime_factor", measure_realtime_factor)
node.create_service(Trigger, "/openarm/isaac_gap/apply_runtime_performance", apply_runtime_performance)
node.create_service(Trigger, "/openarm/isaac_gap/restore_runtime_performance", restore_runtime_performance)
node.create_service(Trigger, "/openarm/isaac_gap/disable_viewport_updates", disable_viewport_updates)
node.create_service(Trigger, "/openarm/isaac_gap/restore_viewport_updates", restore_viewport_updates)
node.create_service(Trigger, "/openarm/isaac_gap/play_timeline", play_timeline)


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
print("OPENARM_GAP_DAEMON_ARMED services=/openarm/isaac_gap/{ensure_state,ensure_bridge,ensure_all,diagnose,repair_right_j7_drive,restore_right_j7_drive,repair_all_arm_drives,restore_all_arm_drives,export_current_stage,enable_compensation_replay,disable_compensation_replay,apply_right_j7_dynamic_drive,restore_right_j7_dynamic_drive,apply_physics_rate,restore_physics_rate,measure_realtime_factor,apply_runtime_performance,restore_runtime_performance,disable_viewport_updates,restore_viewport_updates,play_timeline,status} topics=/openarm/isaac_gap/{events,diagnostic_json,timing_json,realtime_factor_json} domain=%s rmw=%s state_script=%s bridge_script=%s" % (os.environ.get("ROS_DOMAIN_ID", "0"), os.environ.get("RMW_IMPLEMENTATION", "default"), STATE_SCRIPT, BRIDGE_SCRIPT))
