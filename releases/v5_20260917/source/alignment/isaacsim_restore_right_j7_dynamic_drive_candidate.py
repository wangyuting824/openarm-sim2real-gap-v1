"""Restore the J7 dynamic sweep baseline in the live Isaac session only."""
import json
from pathlib import Path

import omni.usd
from pxr import UsdPhysics

SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_right_j7_dynamic_pre_sweep.json")
if not SNAPSHOT.is_file():
    raise RuntimeError("No J7 dynamic pre-sweep snapshot: " + str(SNAPSHOT))
original = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
stage = omni.usd.get_context().get_stage()
prim = stage.GetPrimAtPath(original["joint_path"])
drive = UsdPhysics.DriveAPI.Get(prim, "angular")
if not prim.IsValid() or not drive.GetPrim().IsValid():
    raise RuntimeError("Missing J7 drive during restore")
for getter, key in ((drive.GetTypeAttr, "type"),
                    (drive.GetTargetPositionAttr, "target_position"),
                    (drive.GetTargetVelocityAttr, "target_velocity"),
                    (drive.GetStiffnessAttr, "stiffness"),
                    (drive.GetDampingAttr, "damping"),
                    (drive.GetMaxForceAttr, "max_force")):
    getter().Set(original[key])
print("OPENARM_RIGHT_J7_DYNAMIC_DRIVE_RESTORED")
