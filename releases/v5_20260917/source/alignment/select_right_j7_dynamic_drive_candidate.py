#!/usr/bin/env python3
"""Select one reversible J7 live-drive candidate for the next Isaac-only run."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SWEEP = ROOT / "calibrations" / "openarm_right_j7_dynamic_drive_sweep_v1.json"
ACTIVE = ROOT / "calibrations" / "openarm_right_j7_dynamic_drive_active_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_id")
    parser.add_argument("--sweep", type=Path, default=SWEEP)
    parser.add_argument("--active", type=Path, default=ACTIVE)
    args = parser.parse_args()
    sweep = json.loads(args.sweep.read_text(encoding="utf-8"))
    choices = [sweep["baseline"], *sweep["candidates"]]
    candidate = next((item for item in choices if item["candidate_id"] == args.candidate_id), None)
    if candidate is None:
        raise SystemExit("unknown candidate: %s" % args.candidate_id)
    result = {
        "schema_version": 1,
        "scope": "Isaac-only, live-session dynamic-drive candidate",
        "selected_at_utc": datetime.now(timezone.utc).isoformat(),
        **candidate,
    }
    args.active.parent.mkdir(parents=True, exist_ok=True)
    args.active.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("OPENARM_RIGHT_J7_DYNAMIC_CANDIDATE_SELECTED=" + candidate["candidate_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
