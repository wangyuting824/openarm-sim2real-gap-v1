"""Restore active viewport updates after the Isaac-only render-load probe."""
import json
from pathlib import Path

from omni.kit.viewport.utility import get_active_viewport

SNAPSHOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_viewport_updates_pre_probe.json")
saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
viewport = get_active_viewport()
if viewport is None:
    raise RuntimeError("No active viewport to restore")
viewport.updates_enabled = bool(saved["updates_enabled"])
print("OPENARM_VIEWPORT_UPDATES_RESTORED value=%s" % saved["updates_enabled"])
