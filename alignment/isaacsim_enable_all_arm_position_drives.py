"""Enable conservative, reversible position drives for all Isaac arm joints.

Run only inside Isaac Sim through the gap daemon.  It edits the live USD
session only; it never sends ROS robot commands.  Every angular drive is
snapshotted once and its target is initialized from the live articulation pose
to avoid an unintended jump when gains are enabled.
"""
import builtins
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import omni.usd
from pxr import UsdPhysics


JOINTS = [
    "openarm_left_joint1", "openarm_left_joint2", "openarm_left_joint3",
    "openarm_left_joint4", "openarm_left_joint5", "openarm_left_joint6",
    "openarm_left_joint7", "openarm_right_joint1", "openarm_right_joint2",
    "openarm_right_joint3", "openarm_right_joint4", "openarm_right_joint5",
    "openarm_right_joint6", "openarm_right_joint7",
]
PHYSICS_ROOT = "/openarm_v20/Physics"
SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_all_arm_drives_original.json")
RESULT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_all_arm_drives_repair.json")
STIFFNESS = 100.0
DAMPING = 10.0


def value(attribute):
    return attribute.Get() if attribute and attribute.IsValid() else None


stage = omni.usd.get_context().get_stage()
if stage is None:
    raise RuntimeError("No USD stage is open")

bridge = getattr(builtins, "_openarm_timestamped_bridge", None)
state_pub = getattr(builtins, "_openarm_state_publisher", None)
arm = bridge.get("arm") if bridge else (state_pub.get("arm") if state_pub else None)
if arm is None:
    raise RuntimeError("No initialized articulation is available")

names = list(arm.dof_names)
positions = np.asarray(arm.get_joint_positions()).reshape(-1)
name_to_position = {name: float(positions[names.index(name)]) for name in JOINTS if name in names}
missing_dofs = [name for name in JOINTS if name not in name_to_position]
if missing_dofs:
    raise RuntimeError("Articulation is missing expected arm DOFs: " + repr(missing_dofs))

original = []
repaired = []
for dof_name in JOINTS:
    path = PHYSICS_ROOT + "/" + dof_name
    prim = stage.GetPrimAtPath(path)
    if not prim.IsValid():
        raise RuntimeError("Missing joint prim: " + path)
    drive = UsdPhysics.DriveAPI.Get(prim, "angular")
    if not drive.GetPrim().IsValid():
        raise RuntimeError("Missing angular drive: " + path)
    previous = {
        "joint_path": path,
        "dof_name": dof_name,
        "type": value(drive.GetTypeAttr()),
        "target_position": value(drive.GetTargetPositionAttr()),
        "target_velocity": value(drive.GetTargetVelocityAttr()),
        "stiffness": value(drive.GetStiffnessAttr()),
        "damping": value(drive.GetDampingAttr()),
        "max_force": value(drive.GetMaxForceAttr()),
    }
    original.append(previous)
    current_rad = name_to_position[dof_name]
    drive.GetTypeAttr().Set("force")
    drive.GetTargetPositionAttr().Set(float(np.degrees(current_rad)))
    drive.GetTargetVelocityAttr().Set(0.0)
    drive.GetStiffnessAttr().Set(STIFFNESS)
    drive.GetDampingAttr().Set(DAMPING)
    repaired.append({"dof_name": dof_name, "joint_path": path,
                     "initial_position_rad": current_rad,
                     "initial_target_deg": float(np.degrees(current_rad)),
                     "max_force_unchanged": previous["max_force"]})

SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
if not SNAPSHOT.exists():
    SNAPSHOT.write_text(json.dumps({"drives": original}, indent=2) + "\n", encoding="utf-8")
RESULT.write_text(json.dumps({
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "mode": "isaac_only_live_session",
    "candidate": {"type": "force", "stiffness": STIFFNESS, "damping": DAMPING},
    "snapshot": str(SNAPSHOT), "repaired": repaired,
}, indent=2) + "\n", encoding="utf-8")
print("OPENARM_ALL_ARM_POSITION_DRIVES_ENABLED count=%d stiffness=%s damping=%s" % (
    len(repaired), STIFFNESS, DAMPING))
