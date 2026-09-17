#!/usr/bin/env python3
"""Select an allowlisted live runtime-performance candidate."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SWEEP = ROOT / "calibrations" / "openarm_isaac_runtime_performance_sweep_v1.json"
ACTIVE = ROOT / "calibrations" / "openarm_isaac_runtime_performance_active_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_id")
    args = parser.parse_args()
    sweep = json.loads(SWEEP.read_text(encoding="utf-8"))
    candidate = next((x for x in [sweep["baseline"], *sweep["candidates"]]
                      if x["candidate_id"] == args.candidate_id), None)
    if candidate is None:
        raise SystemExit("unknown runtime candidate: " + args.candidate_id)
    ACTIVE.write_text(json.dumps({"schema_version": 1,
                                  "selected_at_utc": datetime.now(timezone.utc).isoformat(),
                                  "scope": "Isaac-only live runtime performance candidate", **candidate},
                                 indent=2) + "\n", encoding="utf-8")
    print("OPENARM_ISAAC_RUNTIME_CANDIDATE_SELECTED=" + candidate["candidate_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
