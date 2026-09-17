"""Restore the runtime-performance setting saved before the Isaac-only scan."""
import json
from pathlib import Path

import carb

SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_runtime_performance_pre_sweep.json")
saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
carb.settings.get_settings().set(saved["setting"], saved["value"])
print("OPENARM_ISAAC_RUNTIME_RESTORED %s=%s" % (saved["setting"], saved["value"]))
