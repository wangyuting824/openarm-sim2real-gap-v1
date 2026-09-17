"""Read-only Isaac Sim recorder for OpenArm bimanual end-effector metrics.

Open this file in Isaac Sim Script Editor and run it before pressing Play.
It never sends joint actions, modifies USD, or accesses real hardware.
"""
from __future__ import annotations

import builtins
import csv
import json
import math
import time
from pathlib import Path

import omni.kit.app
import omni.timeline
import omni.usd
from pxr import Usd, UsdGeom

DURATION_S = 10.0
AUTO_PLAY = True
LEFT_ROLE = "giver"
RIGHT_ROLE = "receiver"
# Optional World-frame position in metres, e.g. (0.35, 0.0, 0.25).
# Leave None to record only distance and relative speed.
HANDOFF_TARGET_M = None
HANDOFF_POSITION_THRESHOLD_M = 0.02

LEFT_EE_PRIM = (
    "/openarm_v20/Geometry/world/openarm_body_link0/"
    "openarm_left_base_link/openarm_left_link1/openarm_left_link2/"
    "openarm_left_link3/openarm_left_link4/openarm_left_link5/"
    "openarm_left_link6/openarm_left_ee_base_link"
)
RIGHT_EE_PRIM = (
    "/openarm_v20/Geometry/world/openarm_body_link0/"
    "openarm_right_base_link/openarm_right_link1/openarm_right_link2/"
    "openarm_right_link3/openarm_right_link4/openarm_right_link5/"
    "openarm_right_link6/openarm_right_ee_base_link"
)
RESULT_ROOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_migration")


def pose_m(stage, path, metres_per_unit):
    prim = stage.GetPrimAtPath(path)
    if not prim.IsValid():
        raise RuntimeError("Invalid end-effector prim: " + path)
    matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    translation = matrix.ExtractTranslation()
    quat = matrix.ExtractRotationQuat()
    imaginary = quat.GetImaginary()
    return (
        tuple(float(translation[i]) * metres_per_unit for i in range(3)),
        (float(imaginary[0]), float(imaginary[1]), float(imaginary[2]), float(quat.GetReal())),
    )


def norm(values):
    return math.sqrt(sum(value * value for value in values))


def main():
    previous = getattr(builtins, "_openarm_bimanual_capture", None)
    if previous:
        previous["subscription"] = None
        print("Stopped previous OpenArm recorder.")

    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open.")
    for path in (LEFT_EE_PRIM, RIGHT_EE_PRIM):
        if not stage.GetPrimAtPath(path).IsValid():
            raise RuntimeError("Invalid end-effector prim: " + path)

    metres_per_unit = float(UsdGeom.GetStageMetersPerUnit(stage))
    session_id = "isaac_bimanual_" + time.strftime("%Y%m%d_%H%M%S")
    output = RESULT_ROOT / session_id / "bimanual"
    output.mkdir(parents=True, exist_ok=False)
    config = {
        "session_id": session_id, "source": "isaac_sim", "duration_s": DURATION_S,
        "left_role": LEFT_ROLE, "right_role": RIGHT_ROLE,
        "left_ee_prim": LEFT_EE_PRIM, "right_ee_prim": RIGHT_EE_PRIM,
        "stage_meters_per_unit": metres_per_unit, "handoff_target_m": HANDOFF_TARGET_M,
        "handoff_position_threshold_m": HANDOFF_POSITION_THRESHOLD_M,
        "action_sync": "not_measured: read-only recorder has no action timestamps",
    }
    (output / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    state = {"subscription": None, "started": False, "start": None, "wall_start": None, "prev_time": None, "prev_wall": None,
             "prev_left": None, "prev_right": None, "rows": [], "left_arrival": None,
             "right_arrival": None, "output": output, "session_id": session_id}
    timeline = omni.timeline.get_timeline_interface()

    def finish():
        fields = ["physics_tick", "sim_time_s", "elapsed_s", "left_x_m", "left_y_m", "left_z_m",
                  "left_qx", "left_qy", "left_qz", "left_qw", "right_x_m", "right_y_m", "right_z_m",
                  "right_qx", "right_qy", "right_qz", "right_qw", "ee_distance_m", "relative_speed_mps"]
        with (state["output"] / "sync_motion.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(state["rows"])
        rows = state["rows"]
        distances = [row["ee_distance_m"] for row in rows]
        speeds = [row["relative_speed_mps"] for row in rows if row["relative_speed_mps"] is not None]
        left_arrival, right_arrival = state["left_arrival"], state["right_arrival"]
        metrics = {
            "session_id": state["session_id"], "source": "isaac_sim", "sample_count": len(rows),
            "recorded_duration_s": rows[-1]["elapsed_s"] if rows else 0.0,
            "ee_distance_m": {"min": min(distances) if distances else None, "max": max(distances) if distances else None},
            "relative_speed_mps": {"max": max(speeds) if speeds else None, "mean": sum(speeds) / len(speeds) if speeds else None},
            "action_sync": "not_measured: recorder has no action timestamps",
            "left_arrival_time_s": left_arrival, "right_arrival_time_s": right_arrival,
            "ee_arrival_skew_s": abs(left_arrival - right_arrival) if left_arrival is not None and right_arrival is not None else None,
            "handoff_window": "not_configured" if HANDOFF_TARGET_M is None else "arrival proxy only",
        }
        metrics_path = state["output"] / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        state["subscription"] = None
        print("OPENARM_CAPTURE_COMPLETE session=" + state["session_id"])
        print("WROTE " + str(metrics_path))
        print(json.dumps(metrics, indent=2))

    def on_update(_event):
        sim_time = float(timeline.get_current_time())
        if not state["started"]:
            state["started"], state["start"], state["wall_start"] = True, sim_time, time.monotonic()
        # Imported stages that do not yet have a PhysicsScene may not advance
        # Isaac's simulation clock.  Wall elapsed time keeps this read-only
        # recorder usable while the stage/controller is being completed.
        elapsed = time.monotonic() - state["wall_start"]
        left, left_q = pose_m(stage, LEFT_EE_PRIM, metres_per_unit)
        right, right_q = pose_m(stage, RIGHT_EE_PRIM, metres_per_unit)
        separation = tuple(left[i] - right[i] for i in range(3))
        speed = None
        # Prefer simulation time.  During USD import/debugging, a stage can
        # render while its PhysicsScene clock is still stationary; use the
        # Kit-frame wall interval in that case rather than dropping velocity.
        dt = sim_time - state["prev_time"] if state["prev_time"] is not None else None
        wall_now = time.monotonic()
        if dt is None or dt <= 0.0:
            dt = wall_now - state["prev_wall"] if state["prev_wall"] is not None else None
        if dt is not None and dt > 0.0:
            old_sep = tuple(state["prev_left"][i] - state["prev_right"][i] for i in range(3))
            speed = norm(tuple(separation[i] - old_sep[i] for i in range(3))) / dt
        if HANDOFF_TARGET_M is not None:
            if state["left_arrival"] is None and norm(tuple(left[i] - HANDOFF_TARGET_M[i] for i in range(3))) <= HANDOFF_POSITION_THRESHOLD_M:
                state["left_arrival"] = elapsed
            if state["right_arrival"] is None and norm(tuple(right[i] - HANDOFF_TARGET_M[i] for i in range(3))) <= HANDOFF_POSITION_THRESHOLD_M:
                state["right_arrival"] = elapsed
        state["rows"].append({
            "physics_tick": len(state["rows"]), "sim_time_s": sim_time, "elapsed_s": elapsed,
            "left_x_m": left[0], "left_y_m": left[1], "left_z_m": left[2],
            "left_qx": left_q[0], "left_qy": left_q[1], "left_qz": left_q[2], "left_qw": left_q[3],
            "right_x_m": right[0], "right_y_m": right[1], "right_z_m": right[2],
            "right_qx": right_q[0], "right_qy": right_q[1], "right_qz": right_q[2], "right_qw": right_q[3],
            "ee_distance_m": norm(separation), "relative_speed_mps": speed,
        })
        state["prev_time"], state["prev_wall"] = sim_time, wall_now
        state["prev_left"], state["prev_right"] = left, right
        if elapsed >= DURATION_S:
            finish()

    # Kit's update stream runs for every rendered/simulation frame.  It works
    # for the current imported USD even before a PhysicsScene is configured.
    state["subscription"] = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(on_update)
    builtins._openarm_bimanual_capture = state
    print("OPENARM_CAPTURE_ARMED")
    if AUTO_PLAY:
        timeline.play()
        print("Timeline Play requested automatically.")
    print("Recording starts at the next Isaac Sim frame and lasts %.1f s." % DURATION_S)
    print("Output directory: " + str(output))


main()
