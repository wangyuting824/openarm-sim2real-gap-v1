"""Enable a conservative, reversible position drive for Isaac-only right J7.

Run only through the gap daemon. The script keeps the current J7 pose as the
initial target, snapshots the original USD values, and never publishes ROS
commands or touches the real robot.
"""
import builtins
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import omni.usd
from pxr import UsdPhysics

JOINT_PATH = "/openarm_v20/Physics/openarm_right_joint7"
DOF_NAME = "openarm_right_joint7"
SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_right_j7_drive_original.json")
RESULT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_right_j7_drive_repair.json")
STIFFNESS = 100.0
DAMPING = 10.0


def value(attribute):
    return attribute.Get() if attribute and attribute.IsValid() else None


stage = omni.usd.get_context().get_stage()
if stage is None:
    raise RuntimeError("No USD stage is open")
prim = stage.GetPrimAtPath(JOINT_PATH)
if not prim.IsValid():
    raise RuntimeError("Missing joint prim: " + JOINT_PATH)
drive = UsdPhysics.DriveAPI.Get(prim, "angular")
if not drive.GetPrim().IsValid():
    raise RuntimeError("Missing angular drive: " + JOINT_PATH)

bridge = getattr(builtins, "_openarm_timestamped_bridge", None)
state_pub = getattr(builtins, "_openarm_state_publisher", None)
arm = bridge.get("arm") if bridge else (state_pub.get("arm") if state_pub else None)
if arm is None:
    raise RuntimeError("No initialized articulation is available")
try:
    names = list(arm.dof_names)
    index = names.index(DOF_NAME)
    current_rad = float(np.asarray(arm.get_joint_positions()).reshape(-1)[index])
except Exception as error:
    raise RuntimeError("Cannot read %s position: %r" % (DOF_NAME, error))

original = {
    "joint_path": JOINT_PATH,
    "dof_name": DOF_NAME,
    "type": value(drive.GetTypeAttr()),
    "target_position": value(drive.GetTargetPositionAttr()),
    "target_velocity": value(drive.GetTargetVelocityAttr()),
    "stiffness": value(drive.GetStiffnessAttr()),
    "damping": value(drive.GetDampingAttr()),
    "max_force": value(drive.GetMaxForceAttr()),
}
SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
if not SNAPSHOT.exists():
    SNAPSHOT.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")

# USD angular drive targets are authored in degrees. Starting at the live pose
# avoids a step toward the previous authored zero target when gain is enabled.
drive.GetTypeAttr().Set("force")
drive.GetTargetPositionAttr().Set(float(np.degrees(current_rad)))
drive.GetTargetVelocityAttr().Set(0.0)
drive.GetStiffnessAttr().Set(STIFFNESS)
drive.GetDampingAttr().Set(DAMPING)

result = {
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "mode": "isaac_only_live_session",
    "joint_path": JOINT_PATH,
    "dof_name": DOF_NAME,
    "initial_position_rad": current_rad,
    "initial_target_deg": float(np.degrees(current_rad)),
    "candidate": {"type": "force", "stiffness": STIFFNESS, "damping": DAMPING,
                  "max_force_unchanged": original["max_force"]},
    "snapshot": str(SNAPSHOT),
}
RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print("OPENARM_RIGHT_J7_POSITION_DRIVE_ENABLED stiffness=%s damping=%s target_deg=%s" % (
    STIFFNESS, DAMPING, result["initial_target_deg"]
))
