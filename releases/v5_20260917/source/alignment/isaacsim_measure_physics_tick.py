"""Measure Isaac Sim physics-step and Kit-update timing.

Run in Isaac Sim Script Editor while the timeline is playing.  The script does
not alter USD, command the robot, or access real hardware.
"""
import builtins
import json
import statistics
import time
from pathlib import Path

import omni.kit.app
import omni.physx
import omni.timeline

DURATION_S = 10.0
RESULT_ROOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_migration")


def summarize(times):
    intervals = [b - a for a, b in zip(times, times[1:]) if b > a]
    if not intervals:
        return {"count": len(times), "interval_count": 0, "mean_hz": None,
                "min_hz": None, "max_hz": None}
    hz = [1.0 / dt for dt in intervals]
    return {"count": len(times), "interval_count": len(intervals),
            "mean_hz": sum(hz) / len(hz), "min_hz": min(hz), "max_hz": max(hz),
            "mean_interval_s": statistics.fmean(intervals),
            "std_interval_s": statistics.pstdev(intervals) if len(intervals) > 1 else 0.0}


old = getattr(builtins, "_openarm_tick_probe", None)
if old:
    old["physics_sub"] = None
    old["update_sub"] = None

session = "isaac_physics_tick_" + time.strftime("%Y%m%d_%H%M%S")
out = RESULT_ROOT / session / "control"
out.mkdir(parents=True, exist_ok=False)
state = {"physics_sub": None, "update_sub": None, "physics_times": [], "update_times": [],
         "started": None, "finished": False, "out": out, "session": session}


def finish():
    if state["finished"]:
        return
    state["finished"] = True
    metrics = {"session_id": state["session"], "source": "isaac_sim",
               "duration_wall_s": time.monotonic() - state["started"],
               "physics_step": summarize(state["physics_times"]),
               "kit_update": summarize(state["update_times"])}
    path = state["out"] / "tick_metrics.json"
    path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    state["physics_sub"] = None
    state["update_sub"] = None
    print("OPENARM_PHYSICS_TICK_COMPLETE")
    print("RESULT=" + str(path))
    print(json.dumps(metrics, indent=2))


def on_physics_step(_dt):
    state["physics_times"].append(time.monotonic())


def on_update(_event):
    now = time.monotonic()
    if state["started"] is None:
        state["started"] = now
    state["update_times"].append(now)
    if now - state["started"] >= DURATION_S:
        finish()


state["physics_sub"] = omni.physx.get_physx_interface().subscribe_physics_step_events(on_physics_step)
state["update_sub"] = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(on_update)
builtins._openarm_tick_probe = state
omni.timeline.get_timeline_interface().play()
print("OPENARM_PHYSICS_TICK_ARMED duration_s=%.1f" % DURATION_S)
