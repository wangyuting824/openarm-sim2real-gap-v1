#!/usr/bin/env python3
"""Print the read-only physics fingerprint relevant to dynamic tuning."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    j7 = next((x for x in data.get("angular_drives", [])
               if x.get("prim_path", "").endswith("openarm_right_joint7")), None)
    physics = data.get("physics_fingerprint", [])
    print(json.dumps({
        "stage_root_layer": data.get("stage_root_layer"),
        "j7_angular_drive": j7,
        "physics_fingerprint": physics,
        "interpretation": (
            "read-only authored attributes; absent fields are not proof of a runtime default. "
            "Do not tune until velocity/control/solver fields are identified."
        ),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
