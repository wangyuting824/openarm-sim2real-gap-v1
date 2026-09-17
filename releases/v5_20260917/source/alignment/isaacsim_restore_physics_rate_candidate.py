"""Restore the live PhysicsScene rate saved before the Isaac-only sweep."""
import json
from pathlib import Path

import omni.usd
from pxr import Sdf

SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_physics_rate_pre_sweep.json")
saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
stage = omni.usd.get_context().get_stage()
scene = stage.GetPrimAtPath(saved["scene_path"])
attr = scene.GetAttribute(saved["attribute"])
if not attr or not attr.IsValid():
    attr = scene.CreateAttribute(saved["attribute"], Sdf.ValueTypeNames.Int, custom=False)
attr.Set(saved["value"])
print("OPENARM_ISAAC_PHYSICS_RATE_RESTORED value=%s" % saved["value"])
