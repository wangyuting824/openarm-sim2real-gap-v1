#!/usr/bin/env python3
"""Score Isaac-only J7 dynamic candidates against the measured real t90 band."""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glob", default="alignment/results/openarm_isaac_only_right_j7_dynamic_*/dynamic_metrics.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--t90-min-s", type=float, default=0.10)
    parser.add_argument("--t90-max-s", type=float, default=0.15)
    parser.add_argument("--max-overshoot-fraction", type=float, default=0.10)
    args = parser.parse_args()
    rows = []
    for filename in sorted(glob.glob(args.glob)):
        data = json.loads(Path(filename).read_text(encoding="utf-8"))
        records = [x for x in data.get("step_records", []) if x.get("kind") == "step" and x.get("sim", {}).get("valid")]
        t90 = [x["sim"]["t90_s"] for x in records if x["sim"].get("t90_s") is not None]
        fractions = []
        for item in records:
            amplitude = abs(item["sim"].get("response_amplitude_rad", 0.0))
            overshoot = max(0.0, item["sim"].get("overshoot_rad", 0.0))
            if amplitude > 1e-6:
                fractions.append(overshoot / amplitude)
        candidate = Path(filename).parent.name.removeprefix("openarm_isaac_only_right_j7_dynamic_")
        avg_t90, max_over = mean(t90), max(fractions, default=None)
        accepted = (avg_t90 is not None and args.t90_min_s <= avg_t90 <= args.t90_max_s and
                    (max_over is None or max_over <= args.max_overshoot_fraction))
        target = (args.t90_min_s + args.t90_max_s) / 2.0
        score = None if avg_t90 is None else abs(avg_t90 - target) + (max_over or 0.0)
        rows.append({"candidate_id": candidate, "source": filename, "valid_step_count": len(t90),
                     "t90_s_mean": avg_t90, "max_overshoot_fraction": max_over,
                     "accepted": accepted, "score": score})
    accepted_rows = [x for x in rows if x["accepted"]]
    best_pool = accepted_rows or [x for x in rows if x["score"] is not None]
    best = min(best_pool, key=lambda x: x["score"]) if best_pool else None
    output = {"schema_version": 1, "kind": "openarm_isaac_j7_dynamic_candidate_score",
              "target_t90_s": [args.t90_min_s, args.t90_max_s],
              "max_overshoot_fraction": args.max_overshoot_fraction,
              "candidates": rows, "selected_candidate": best,
              "status": "accepted_candidate_available" if accepted_rows else "no_candidate_passed"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": output["status"], "selected_candidate": best}, indent=2))
    return 0 if accepted_rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
