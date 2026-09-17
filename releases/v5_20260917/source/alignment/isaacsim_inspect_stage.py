"""Print the currently opened Isaac Sim stage structure.

Run this from Isaac Sim's Script Editor after the OpenArm USD is open.  The
script is read-only: it does not create, move, or control any articulation.
"""

from pathlib import Path

import omni.usd
from pxr import UsdPhysics


def main() -> None:
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        print("NO_STAGE")
        return

    out = Path("/tmp/openarm_isaac_stage_inspection.txt")
    lines = []
    lines.append(f"stage={stage.GetRootLayer().identifier}")
    lines.append("[articulation_roots]")
    for prim in stage.Traverse():
        try:
            is_root = prim.HasAPI(UsdPhysics.ArticulationRootAPI)
        except Exception:
            is_root = False
        if is_root:
            lines.append(f"{prim.GetPath()} type={prim.GetTypeName()}")

    lines.append("[joints]")
    joint_types = {
        "PhysicsRevoluteJoint",
        "PhysicsPrismaticJoint",
        "PhysicsSphericalJoint",
        "PhysicsFixedJoint",
        "PhysicsJoint",
    }
    for prim in stage.Traverse():
        if prim.GetTypeName() in joint_types:
            lines.append(f"{prim.GetPath()} type={prim.GetTypeName()}")

    lines.append("[openarm_named_prims]")
    for prim in stage.Traverse():
        text = str(prim.GetPath()).lower()
        if "openarm" in text or "finger" in text or "gripper" in text:
            lines.append(f"{prim.GetPath()} type={prim.GetTypeName()}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("WROTE", out)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
