"""Measure Isaac timeline progress against wall time without changing the stage.

Run through the gap-control daemon while the timeline is already playing.  The
result distinguishes a slow physics/control response from a simulation that is
simply advancing slower than real time on the current host.
"""
import builtins
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import omni.kit.app
import omni.timeline
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

OUTPUT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_realtime_factor_probe.json")
TOPIC = "/openarm/isaac_gap/realtime_factor_json"
WALL_WINDOW_S = 10.0


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[index]


old = getattr(builtins, "_openarm_realtime_factor_probe", None)
if old is not None:
    old["sub"] = None
    old["physics_sub"] = None

daemon = getattr(builtins, "_openarm_gap_control_daemon", None)
if daemon is None:
    raise RuntimeError("gap control daemon is required")

qos = QoSProfile(depth=1)
qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
qos.reliability = ReliabilityPolicy.RELIABLE
publisher = daemon["node"].create_publisher(String, TOPIC, qos)
timeline = omni.timeline.get_timeline_interface()
probe = {
    "started_wall_monotonic_s": time.monotonic(),
    "started_timeline_s": float(timeline.get_current_time()),
    "previous_wall_monotonic_s": None,
    "previous_timeline_s": None,
    "wall_intervals_s": [],
    "timeline_intervals_s": [],
    "physics_step_count": 0,
    "physics_advanced_s": 0.0,
    "physics_steps_s": [],
    "physics_subscription_error": None,
    "sub": None,
    "physics_sub": None,
    "publisher": publisher,
    "complete": False,
}


def on_physics_step(dt):
    """Accumulate the actual PhysX dt, independent of the UI timeline API."""
    try:
        value = float(dt)
        if value >= 0.0:
            probe["physics_step_count"] += 1
            probe["physics_advanced_s"] += value
            probe["physics_steps_s"].append(value)
    except Exception as error:
        probe["physics_subscription_error"] = repr(error)


try:
    import omni.physx
    probe["physics_sub"] = omni.physx.get_physx_interface().subscribe_physics_step_events(on_physics_step)
except Exception as error:
    probe["physics_subscription_error"] = repr(error)


def on_update(_event):
    if probe["complete"]:
        return
    wall = time.monotonic()
    sim = float(timeline.get_current_time())
    previous_wall = probe["previous_wall_monotonic_s"]
    previous_sim = probe["previous_timeline_s"]
    if previous_wall is not None and previous_sim is not None:
        probe["wall_intervals_s"].append(wall - previous_wall)
        probe["timeline_intervals_s"].append(sim - previous_sim)
    probe["previous_wall_monotonic_s"] = wall
    probe["previous_timeline_s"] = sim
    wall_elapsed = wall - probe["started_wall_monotonic_s"]
    if wall_elapsed < WALL_WINDOW_S:
        return
    sim_elapsed = sim - probe["started_timeline_s"]
    positive_wall = [x for x in probe["wall_intervals_s"] if x > 0.0]
    positive_sim = [x for x in probe["timeline_intervals_s"] if x >= 0.0]
    payload = {
        "schema_version": 1,
        "kind": "openarm_isaac_realtime_factor_probe",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "wall_window_s": wall_elapsed,
        "timeline_advanced_s": sim_elapsed,
        "realtime_factor": sim_elapsed / wall_elapsed if wall_elapsed > 0.0 else None,
        "physics_advanced_s": probe["physics_advanced_s"],
        "physics_realtime_factor": (probe["physics_advanced_s"] / wall_elapsed
                                    if wall_elapsed > 0.0 else None),
        "physics_step_count": probe["physics_step_count"],
        "physics_step_hz": (probe["physics_step_count"] / wall_elapsed
                            if wall_elapsed > 0.0 else None),
        "physics_step_ms": {
            "median": statistics.median(probe["physics_steps_s"]) * 1000.0 if probe["physics_steps_s"] else None,
            "p95": percentile(probe["physics_steps_s"], 0.95) * 1000.0 if probe["physics_steps_s"] else None,
            "max": max(probe["physics_steps_s"]) * 1000.0 if probe["physics_steps_s"] else None,
        },
        "physics_subscription_error": probe["physics_subscription_error"],
        "kit_update_count": len(positive_wall),
        "kit_update_hz": len(positive_wall) / wall_elapsed if wall_elapsed > 0.0 else None,
        "kit_update_interval_ms": {
            "median": statistics.median(positive_wall) * 1000.0 if positive_wall else None,
            "p95": percentile(positive_wall, 0.95) * 1000.0 if positive_wall else None,
            "max": max(positive_wall) * 1000.0 if positive_wall else None,
        },
        "timeline_step_ms": {
            "median": statistics.median(positive_sim) * 1000.0 if positive_sim else None,
            "p95": percentile(positive_sim, 0.95) * 1000.0 if positive_sim else None,
            "max": max(positive_sim) * 1000.0 if positive_sim else None,
        },
        "timeline_playing": bool(timeline.is_playing()),
        "interpretation": (
            "physics_step_subscription_unavailable" if probe["physics_subscription_error"] else
            "physics_not_advancing" if probe["physics_advanced_s"] <= 0.0 else
            "physics_below_realtime" if probe["physics_advanced_s"] / wall_elapsed < 0.95 else
            "physics_approximately_realtime_or_faster"
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    message = String()
    message.data = json.dumps(payload, separators=(",", ":"))
    publisher.publish(message)
    probe["complete"] = True
    probe["sub"] = None
    probe["physics_sub"] = None
    print("OPENARM_REALTIME_FACTOR_PROBE " + message.data)


probe["sub"] = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(on_update)
builtins._openarm_realtime_factor_probe = probe
print("OPENARM_REALTIME_FACTOR_PROBE_ARMED wall_window_s=%.1f topic=%s" % (WALL_WINDOW_S, TOPIC))
