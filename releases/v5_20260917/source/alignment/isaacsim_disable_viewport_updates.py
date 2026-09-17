"""Disable the active Isaac viewport temporarily for a render-load A/B probe."""
import json
from datetime import datetime, timezone
from pathlib import Path

from omni.kit.viewport.utility import get_active_viewport

SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_viewport_updates_pre_probe.json")
RESULT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_viewport_updates_disabled.json")

viewport = get_active_viewport()
if viewport is None:
    raise RuntimeError("No active viewport to disable")
previous = bool(viewport.updates_enabled)
if not SNAPSHOT.exists():
    SNAPSHOT.write_text(json.dumps({"updates_enabled": previous}, indent=2) + "\n", encoding="utf-8")
viewport.updates_enabled = False
RESULT.write_text(json.dumps({"created_at_utc": datetime.now(timezone.utc).isoformat(),
                              "mode": "isaac_only_live_session", "persistent_usd_edit": False,
                              "updates_enabled": False, "snapshot": str(SNAPSHOT)}, indent=2) + "\n",
                  encoding="utf-8")
print("OPENARM_VIEWPORT_UPDATES_DISABLED previous=%s" % previous)
