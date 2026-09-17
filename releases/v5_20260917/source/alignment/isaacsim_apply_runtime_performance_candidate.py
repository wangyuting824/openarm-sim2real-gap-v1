"""Apply an allowlisted, reversible Isaac runtime setting; never edit USD."""
import json
from datetime import datetime, timezone
from pathlib import Path

import carb

CONFIG = Path("/home/tangyuan/openarm_ws/alignment/calibrations/openarm_isaac_runtime_performance_active_v1.json")
SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_runtime_performance_pre_sweep.json")
RESULT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_runtime_performance_applied.json")
SETTING = "/persistent/simulation/minFrameRate"

candidate = json.loads(CONFIG.read_text(encoding="utf-8"))
value = int(candidate["min_frame_rate"])
if value not in (10, 15, 30):
    raise RuntimeError("refuse unreviewed minFrameRate: %s" % value)
settings = carb.settings.get_settings()
if not SNAPSHOT.exists():
    SNAPSHOT.write_text(json.dumps({"setting": SETTING, "value": settings.get(SETTING)}, indent=2) + "\n",
                        encoding="utf-8")
settings.set(SETTING, value)
RESULT.write_text(json.dumps({"created_at_utc": datetime.now(timezone.utc).isoformat(),
                              "mode": "isaac_only_live_session", "persistent_usd_edit": False,
                              "candidate": candidate, "setting": SETTING, "value": value,
                              "snapshot": str(SNAPSHOT)}, indent=2) + "\n", encoding="utf-8")
print("OPENARM_ISAAC_RUNTIME_APPLIED id=%s minFrameRate=%d" % (candidate["candidate_id"], value))
