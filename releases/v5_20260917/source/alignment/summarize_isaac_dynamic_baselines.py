#!/usr/bin/env python3
"""Summarize per-joint Isaac-only dynamic baselines without inferring real gaps."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for path in sorted(args.input_dir.glob("*_dynamic_metrics.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        steps = [x["sim"] for x in data.get("step_records", [])
                 if x.get("kind") == "step" and x.get("sim", {}).get("valid")]
        fractions = [max(0.0, x.get("overshoot_rad", 0.0)) / abs(x["response_amplitude_rad"])
                     for x in steps if abs(x.get("response_amplitude_rad", 0.0)) > 1e-6]
        baseline = data.get("isaac_only_baseline", {})
        rows.append({
            "joint": data.get("joint"), "source": str(path),
            "valid_step_count": baseline.get("valid_step_count", 0),
            "onset_s_mean": baseline.get("onset_s_mean"),
            "t90_s_mean": baseline.get("t90_s_mean"),
            "max_overshoot_fraction": max(fractions, default=None),
            "classification": "isaac_only_baseline_not_real_gap",
        })
    rows.sort(key=lambda x: (x["t90_s_mean"] is None, x["t90_s_mean"] or 0.0), reverse=True)
    output = {
        "schema_version": 1,
        "kind": "openarm_isaac_only_dynamic_baseline_all14",
        "scope": "Isaac-only; does not estimate real-minus-Isaac dynamic gap",
        "joint_count": len(rows), "joints": rows,
        "next_gate": "compare each measured real joint only after raw paired dynamic capture with static replay disabled",
    }
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"joint_count": len(rows), "slowest": rows[:3]}, indent=2))
    return 0 if len(rows) == 14 else 2


if __name__ == "__main__":
    raise SystemExit(main())
