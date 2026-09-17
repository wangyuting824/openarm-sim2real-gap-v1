#!/usr/bin/env python3
"""Analyze a frozen-v4 R J5 independent-power holdout without refitting."""
import argparse
import json
from pathlib import Path

import numpy as np


def stats(values):
    values = np.asarray(values, dtype=float)
    return {
        "count": int(values.size),
        "mae_rad": float(np.mean(np.abs(values))),
        "max_abs_rad": float(np.max(np.abs(values))),
        "mean_rad": float(np.mean(values)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tracking-tolerance-rad", type=float, default=0.01)
    parser.add_argument("--paired-screening-tolerance-rad", type=float, default=0.01)
    args = parser.parse_args()
    record = json.loads(args.input.read_text(encoding="utf-8"))
    runs = record.get("waypoint_runs", [])
    complete = [r for r in runs if r.get("final_real_rad") is not None and r.get("final_sim_rad") is not None]
    if not complete:
        raise RuntimeError("no complete paired waypoint records")
    raw = [r["final_real_rad"] - r["target_rad"] for r in complete]
    paired = [r["final_sim_rad"] - r["final_real_rad"] for r in complete]
    sim_tracking = [r["sim_error_rad"] for r in complete if r.get("sim_error_rad") is not None]
    raw_stats, paired_stats, tracking_stats = stats(raw), stats(paired), stats(sim_tracking)
    gates = {
        "trial_recorder_passed": bool(record.get("passed")),
        "all_waypoints_complete": len(complete) == 18,
        "sim_tracking_max_abs_le_0p01": tracking_stats["max_abs_rad"] <= args.tracking_tolerance_rad,
        "emulated_mae_no_worse_than_raw": paired_stats["mae_rad"] <= raw_stats["mae_rad"],
        "paired_max_abs_le_0p01_screening": paired_stats["max_abs_rad"] <= args.paired_screening_tolerance_rad,
    }
    result = {
        "kind": "openarm_right_j5_v4_independent_power_holdout_summary",
        "trial_id": record.get("trial_id"),
        "input": str(args.input),
        "frozen_calibration": record.get("sim_replay_calibration"),
        "sample_count": len(complete),
        "raw_nominal_minus_real": raw_stats,
        "emulated_sim_minus_real": paired_stats,
        "sim_tracking": tracking_stats,
        "gates": gates,
        "independent_session_validated": all(gates.values()),
        "interpretation": (
            "frozen v4 validated on a fresh independent power session"
            if all(gates.values()) else
            "candidate not promoted; retain evidence and investigate failed gates"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print("OPENARM_RIGHT_J5_V4_INDEPENDENT_HOLDOUT=" + ("PASS" if all(gates.values()) else "FAIL"))
    return 0 if all(gates.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
