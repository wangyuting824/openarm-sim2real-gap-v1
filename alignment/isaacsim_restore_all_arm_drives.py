"""Restore all live Isaac arm drives saved by the all-arm repair script."""
import json
from pathlib import Path

import omni.usd
from pxr import UsdPhysics


SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_all_arm_drives_original.json")
if not SNAPSHOT.is_file():
    raise RuntimeError("No all-arm drive snapshot exists: " + str(SNAPSHOT))
stage = omni.usd.get_context().get_stage()
if stage is None:
    raise RuntimeError("No USD stage is open")
for original in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["drives"]:
    prim = stage.GetPrimAtPath(original["joint_path"])
    drive = UsdPhysics.DriveAPI.Get(prim, "angular")
    for getter, key in ((drive.GetTypeAttr, "type"),
                        (drive.GetTargetPositionAttr, "target_position"),
                        (drive.GetTargetVelocityAttr, "target_velocity"),
                        (drive.GetStiffnessAttr, "stiffness"),
                        (drive.GetDampingAttr, "damping"),
                        (drive.GetMaxForceAttr, "max_force")):
        getter().Set(original[key])
print("OPENARM_ALL_ARM_POSITION_DRIVES_RESTORED")
