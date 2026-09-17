"""Capture a configured bimanual handoff pose/window from PhysX link poses.

Set HANDOFF_TARGET_M and HANDOFF_TARGET_XYZW from the task specification
before running.  The script is read-only and does not send arm commands.
"""
import builtins
import csv
import json
import math
import time
from pathlib import Path

import numpy as np
import omni.kit.app
import omni.timeline

LEFT_EE_PRIM = "/openarm_v20/Geometry/world/openarm_body_link0/openarm_left_base_link/openarm_left_link1/openarm_left_link2/openarm_left_link3/openarm_left_link4/openarm_left_link5/openarm_left_link6/openarm_left_ee_base_link"
RIGHT_EE_PRIM = "/openarm_v20/Geometry/world/openarm_body_link0/openarm_right_base_link/openarm_right_link1/openarm_right_link2/openarm_right_link3/openarm_right_link4/openarm_right_link5/openarm_right_link6/openarm_right_ee_base_link"
HANDOFF_TARGET_M = None                 # e.g. (0.003, 0.000, 0.262)
HANDOFF_TARGET_XYZW = None              # e.g. (0.0, 0.0, 0.0, 1.0)
POSITION_TOLERANCE_M = 0.02
ORIENTATION_TOLERANCE_RAD = math.radians(10.0)
DURATION_S = 12.0
RESULT_ROOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_migration")


def orientation_error_rad(actual, target):
    dot = abs(float(np.dot(actual, target)))
    return 2.0 * math.acos(min(1.0, max(-1.0, dot)))


if HANDOFF_TARGET_M is None or HANDOFF_TARGET_XYZW is None:
    raise RuntimeError("Set HANDOFF_TARGET_M and HANDOFF_TARGET_XYZW before running this test")
target_p = np.asarray(HANDOFF_TARGET_M, dtype=float)
target_q = np.asarray(HANDOFF_TARGET_XYZW, dtype=float)
if np.linalg.norm(target_q) == 0:
    raise RuntimeError("HANDOFF_TARGET_XYZW cannot be zero")
target_q /= np.linalg.norm(target_q)

try:
    from isaacsim.core.prims import RigidPrim
except ImportError:
    from omni.isaac.core.prims import RigidPrim

old = getattr(builtins, "_openarm_handoff_capture", None)
if old:
    old["sub"] = None
left = RigidPrim(prim_paths_expr=LEFT_EE_PRIM, name="openarm_handoff_left")
right = RigidPrim(prim_paths_expr=RIGHT_EE_PRIM, name="openarm_handoff_right")
timeline = omni.timeline.get_timeline_interface()
timeline.play()
session = "isaac_handoff_" + time.strftime("%Y%m%d_%H%M%S")
out = RESULT_ROOT / session / "bimanual"
out.mkdir(parents=True, exist_ok=False)
state = {"sub": None, "initialized": False, "start": None, "rows": [], "window_start": None,
         "windows": [], "finished": False}


def finish():
    if state["finished"]:
        return
    state["finished"] = True
    if state["window_start"] is not None and state["rows"]:
        state["windows"].append({"start_s": state["window_start"], "end_s": state["rows"][-1]["elapsed_s"]})
    with (out / "handoff_samples.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(state["rows"][0]) if state["rows"] else [])
        if state["rows"]:
            writer.writeheader(); writer.writerows(state["rows"])
    metrics = {"session_id": session, "source": "isaac_sim", "sample_count": len(state["rows"]),
               "handoff_target_position_m": target_p.tolist(), "handoff_target_orientation_xyzw": target_q.tolist(),
               "position_tolerance_m": POSITION_TOLERANCE_M, "orientation_tolerance_rad": ORIENTATION_TOLERANCE_RAD,
               "handoff_windows_s": state["windows"],
               "definition": "both end effectors meet configured position and orientation tolerance in the same PhysX sample"}
    path = out / "handoff_metrics.json"
    path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    state["sub"] = None
    print("OPENARM_HANDOFF_CAPTURE_COMPLETE")
    print("RESULT=" + str(path))
    print(json.dumps(metrics, indent=2))


def on_update(_event):
    if not state["initialized"]:
        left.initialize(); right.initialize(); state["initialized"] = True; state["start"] = time.monotonic()
        print("OPENARM_HANDOFF_CAPTURE_READY")
    elapsed = time.monotonic() - state["start"]
    lp, lq = left.get_world_poses(usd=False); rp, rq = right.get_world_poses(usd=False)
    lp, lq, rp, rq = np.asarray(lp[0], dtype=float), np.asarray(lq[0], dtype=float), np.asarray(rp[0], dtype=float), np.asarray(rq[0], dtype=float)
    le_p, re_p = float(np.linalg.norm(lp - target_p)), float(np.linalg.norm(rp - target_p))
    le_q, re_q = orientation_error_rad(lq, target_q), orientation_error_rad(rq, target_q)
    inside = le_p <= POSITION_TOLERANCE_M and re_p <= POSITION_TOLERANCE_M and le_q <= ORIENTATION_TOLERANCE_RAD and re_q <= ORIENTATION_TOLERANCE_RAD
    if inside and state["window_start"] is None: state["window_start"] = elapsed
    if not inside and state["window_start"] is not None:
        state["windows"].append({"start_s": state["window_start"], "end_s": elapsed}); state["window_start"] = None
    state["rows"].append({"elapsed_s": elapsed, "left_position_error_m": le_p, "right_position_error_m": re_p,
                          "left_orientation_error_rad": le_q, "right_orientation_error_rad": re_q,
                          "both_inside": inside})
    if elapsed >= DURATION_S: finish()


state["sub"] = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(on_update)
builtins._openarm_handoff_capture = state
print("OPENARM_HANDOFF_CAPTURE_ARMED")
