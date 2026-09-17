"""Apply a reversible Isaac-only PhysicsScene timestep candidate."""
import json
from datetime import datetime, timezone
from pathlib import Path

import omni.usd
from pxr import Sdf

SCENE_PATH = "/PhysicsScene"
CONFIG = Path("/home/tangyuan/openarm_ws/alignment/calibrations/openarm_isaac_physics_rate_active_v1.json")
SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_physics_rate_pre_sweep.json")
RESULT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_physics_rate_applied.json")
ATTRIBUTE = "physxScene:timeStepsPerSecond"

candidate = json.loads(CONFIG.read_text(encoding="utf-8"))
rate = int(candidate["physx_time_steps_per_second"])
if rate not in (60, 120, 240):
    raise RuntimeError("refuse unreviewed PhysX rate: %s" % rate)
stage = omni.usd.get_context().get_stage()
if stage is None:
    raise RuntimeError("No USD stage is open")
scene = stage.GetPrimAtPath(SCENE_PATH)
if not scene.IsValid():
    raise RuntimeError("Missing PhysicsScene: " + SCENE_PATH)
attr = scene.GetAttribute(ATTRIBUTE)
if not attr or not attr.IsValid():
    attr = scene.CreateAttribute(ATTRIBUTE, Sdf.ValueTypeNames.Int, custom=False)
if not attr or not attr.IsValid():
    raise RuntimeError("Cannot access " + ATTRIBUTE)
if not SNAPSHOT.exists():
    SNAPSHOT.write_text(json.dumps({"scene_path": SCENE_PATH, "attribute": ATTRIBUTE,
                                    "value": attr.Get()}, indent=2) + "\n", encoding="utf-8")
attr.Set(rate)
RESULT.write_text(json.dumps({"created_at_utc": datetime.now(timezone.utc).isoformat(),
                              "mode": "isaac_only_live_session", "persistent_usd_edit": False,
                              "candidate": candidate, "scene_path": SCENE_PATH,
                              "attribute": ATTRIBUTE, "snapshot": str(SNAPSHOT)}, indent=2) + "\n",
                  encoding="utf-8")
print("OPENARM_ISAAC_PHYSICS_RATE_APPLIED id=%s hz=%d" % (candidate["candidate_id"], rate))
