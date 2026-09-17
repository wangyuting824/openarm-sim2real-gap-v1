"""Restore the original USD drive values saved by the J7 Isaac-only repair."""
import json
from pathlib import Path

import omni.usd
from pxr import UsdPhysics

SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_right_j7_drive_original.json")
if not SNAPSHOT.is_file():
    raise RuntimeError("No J7 drive snapshot exists: " + str(SNAPSHOT))
original = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
stage = omni.usd.get_context().get_stage()
prim = stage.GetPrimAtPath(original["joint_path"])
drive = UsdPhysics.DriveAPI.Get(prim, "angular")
for getter, key in ((drive.GetTypeAttr, "type"),
                    (drive.GetTargetPositionAttr, "target_position"),
                    (drive.GetTargetVelocityAttr, "target_velocity"),
                    (drive.GetStiffnessAttr, "stiffness"),
                    (drive.GetDampingAttr, "damping"),
                    (drive.GetMaxForceAttr, "max_force")):
    getter().Set(original[key])
print("OPENARM_RIGHT_J7_POSITION_DRIVE_RESTORED")
