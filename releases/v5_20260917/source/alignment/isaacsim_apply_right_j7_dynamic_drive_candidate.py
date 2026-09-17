"""Apply one reversible Isaac-only J7 dynamic-drive candidate.

The active candidate JSON is deliberately separate from the static replay
calibration.  This script changes only the live USD session and never sends a
ROS command or touches the real robot.
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
CONFIG = Path("/home/tangyuan/openarm_ws/alignment/calibrations/openarm_right_j7_dynamic_drive_active_v1.json")
SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_right_j7_dynamic_pre_sweep.json")
RESULT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_right_j7_dynamic_drive_applied.json")


def value(attribute):
    return attribute.Get() if attribute and attribute.IsValid() else None


if not CONFIG.is_file():
    raise FileNotFoundError("Missing active candidate config: " + str(CONFIG))
candidate = json.loads(CONFIG.read_text(encoding="utf-8"))
for key in ("candidate_id", "stiffness", "damping", "max_force"):
    if key not in candidate:
        raise RuntimeError("Candidate missing " + key)
if any(float(candidate[key]) <= 0.0 for key in ("stiffness", "damping", "max_force")):
    raise RuntimeError("Drive candidate values must be positive")

stage = omni.usd.get_context().get_stage()
if stage is None:
    raise RuntimeError("No USD stage is open")
prim = stage.GetPrimAtPath(JOINT_PATH)
drive = UsdPhysics.DriveAPI.Get(prim, "angular")
if not prim.IsValid() or not drive.GetPrim().IsValid():
    raise RuntimeError("Missing angular drive: " + JOINT_PATH)

bridge = getattr(builtins, "_openarm_timestamped_bridge", None)
state_pub = getattr(builtins, "_openarm_state_publisher", None)
arm = bridge.get("arm") if bridge else (state_pub.get("arm") if state_pub else None)
if arm is None:
    raise RuntimeError("No initialized articulation is available")
names = list(arm.dof_names)
if DOF_NAME not in names:
    raise RuntimeError("Missing articulation DOF: " + DOF_NAME)
current_rad = float(np.asarray(arm.get_joint_positions()).reshape(-1)[names.index(DOF_NAME)])

before = {
    "joint_path": JOINT_PATH, "dof_name": DOF_NAME,
    "type": value(drive.GetTypeAttr()),
    "target_position": value(drive.GetTargetPositionAttr()),
    "target_velocity": value(drive.GetTargetVelocityAttr()),
    "stiffness": value(drive.GetStiffnessAttr()),
    "damping": value(drive.GetDampingAttr()),
    "max_force": value(drive.GetMaxForceAttr()),
}
SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
if not SNAPSHOT.exists():
    SNAPSHOT.write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")

# Move the authoring target to the live pose before changing gains so candidate
# application itself cannot cause an unintended jump.  Bridge commands later
# own the target in normal operation.
drive.GetTypeAttr().Set("force")
drive.GetTargetPositionAttr().Set(float(np.degrees(current_rad)))
drive.GetTargetVelocityAttr().Set(0.0)
drive.GetStiffnessAttr().Set(float(candidate["stiffness"]))
drive.GetDampingAttr().Set(float(candidate["damping"]))
drive.GetMaxForceAttr().Set(float(candidate["max_force"]))

result = {
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "mode": "isaac_only_live_session",
    "candidate": candidate,
    "before": before,
    "initial_position_rad": current_rad,
    "snapshot": str(SNAPSHOT),
    "persistent_usd_edit": False,
}
RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print("OPENARM_RIGHT_J7_DYNAMIC_DRIVE_APPLIED id=%s stiffness=%s damping=%s max_force=%s" % (
    candidate["candidate_id"], candidate["stiffness"], candidate["damping"], candidate["max_force"]))
