"""Read-only Isaac articulation and USD drive inspection for Sim2Real diagnosis.

This runs inside Isaac Sim, normally through isaacsim_gap_control_daemon.py.
It writes a JSON snapshot and never modifies the stage or sends a command.
"""
import builtins
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import carb
import omni.usd
from pxr import UsdPhysics

OUTPUT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_joint_drive_probe.json")
ROOT_HINT = "/openarm_v20/Geometry/world/openarm_body_link0"


def _value(attribute):
    if not attribute or not attribute.IsValid():
        return None
    try:
        raw = attribute.Get()
        if hasattr(raw, "__iter__") and not isinstance(raw, (str, bytes)):
            return [float(item) if isinstance(item, (int, float)) else str(item) for item in raw]
        if isinstance(raw, (int, float, bool, str)) or raw is None:
            return raw
        return str(raw)
    except Exception as error:
        return "<read-error:%r>" % error


def _drive_snapshot(prim):
    drive = UsdPhysics.DriveAPI.Get(prim, "angular")
    if not drive or not drive.GetPrim().IsValid():
        return None
    return {
        "prim_path": str(prim.GetPath()),
        "type": _value(drive.GetTypeAttr()),
        "target_position": _value(drive.GetTargetPositionAttr()),
        "target_velocity": _value(drive.GetTargetVelocityAttr()),
        "stiffness": _value(drive.GetStiffnessAttr()),
        "damping": _value(drive.GetDampingAttr()),
        "max_force": _value(drive.GetMaxForceAttr()),
    }


def _physics_snapshot(prim):
    """Capture authored physics-related attributes without assuming a PhysX version."""
    relevant = {}
    for attribute in prim.GetAttributes():
        name = attribute.GetName()
        lowered = name.lower()
        if any(token in lowered for token in (
            "solver", "substep", "timestep", "time_step", "velocity", "iteration",
            "ccd", "stabil", "gravity", "maxjoint", "maxangular",
        )):
            relevant[name] = _value(attribute)
    return {"prim_path": str(prim.GetPath()), "type_name": str(prim.GetTypeName()),
            "attributes": relevant}


def _render_product_snapshot(prim):
    """Capture the render products separately from PhysX settings.

    This is intentionally read-only.  An interactive viewport can be disabled
    during RL collection while Replicator render products remain enabled for
    policy observations, so their camera/resolution configuration must be
    visible in the performance diagnosis.
    """
    if str(prim.GetTypeName()) != "RenderProduct":
        return None
    relevant = {}
    for attribute in prim.GetAttributes():
        name = attribute.GetName()
        lowered = name.lower()
        if any(token in lowered for token in (
            "camera", "resolution", "enable", "aov", "format", "product",
            "hydra", "renderer", "render",
        )):
            relevant[name] = _value(attribute)
    return {
        "prim_path": str(prim.GetPath()),
        "type_name": str(prim.GetTypeName()),
        "attributes": relevant,
    }


def _runtime_performance_settings():
    """Read runtime throttles that can make physics lag behind wall time."""
    settings = carb.settings.get_settings()
    keys = (
        "/persistent/simulation/minFrameRate",
        "/app/runLoops/main/rateLimitFrequency",
        "/app/viewport/displayOptions",
        "/rtx/post/dlss/execMode",
        "/renderer/multiGpu/enabled",
    )
    output = {}
    for key in keys:
        try:
            value = settings.get(key)
            if value is None or isinstance(value, (bool, int, float, str)):
                output[key] = value
            elif hasattr(value, "__iter__"):
                output[key] = [str(item) for item in value]
            else:
                output[key] = str(value)
        except Exception as error:
            output[key] = "<read-error:%r>" % error
    return output


stage = omni.usd.get_context().get_stage()
if stage is None:
    raise RuntimeError("No USD stage is open")

bridge = getattr(builtins, "_openarm_timestamped_bridge", None)
state_pub = getattr(builtins, "_openarm_state_publisher", None)
static_hold = getattr(builtins, "_openarm_static_hold", None)

articulation = bridge.get("arm") if bridge else (state_pub.get("arm") if state_pub else None)
articulation_snapshot = {"available": articulation is not None}
if articulation is not None:
    try:
        articulation_snapshot.update({
            "dof_names": list(articulation.dof_names),
            "joint_positions_rad": [float(x) for x in np.asarray(articulation.get_joint_positions()).reshape(-1)],
            "joint_velocities_rad_s": [float(x) for x in np.asarray(articulation.get_joint_velocities()).reshape(-1)],
        })
    except Exception as error:
        articulation_snapshot["read_error"] = repr(error)

bridge_snapshot = {"available": bridge is not None}
if bridge is not None:
    active = bridge.get("active_target")
    bridge_snapshot.update({
        "initialized": bool(bridge.get("initialized")),
        "sequence": int(bridge.get("sequence", 0)),
        "apply_count": int(bridge.get("apply_count", 0)),
        "active_target": None if active is None else {
            "positions_rad": [float(x) for x in active[0]],
            "indices": [int(x) for x in active[1]],
        },
        "printed_error": bool(bridge.get("printed_error")),
    })

drives = []
physics_prims = []
render_products = []
for prim in stage.Traverse():
    snapshot = _drive_snapshot(prim)
    if snapshot is not None:
        drives.append(snapshot)
    physics = _physics_snapshot(prim)
    if physics["attributes"] or "physics" in physics["type_name"].lower():
        physics_prims.append(physics)
    render_product = _render_product_snapshot(prim)
    if render_product is not None:
        render_products.append(render_product)

payload = {
    "schema_version": 1,
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "read_only": True,
    "stage_root_layer": str(stage.GetRootLayer().identifier),
    "root_hint": ROOT_HINT,
    "bridge": bridge_snapshot,
    "state_publisher_available": state_pub is not None,
    "static_hold_present": static_hold is not None,
    "articulation": articulation_snapshot,
    "angular_drives": drives,
    "physics_fingerprint": physics_prims,
    "render_products": render_products,
    "runtime_performance_settings": _runtime_performance_settings(),
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("OPENARM_ISAAC_DRIVE_PROBE_WRITTEN " + str(OUTPUT) + " drives=%d" % len(drives))
