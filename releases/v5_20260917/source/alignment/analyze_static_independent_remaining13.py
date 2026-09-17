#!/usr/bin/env python3
"""Summarize frozen-v4 independent-power evidence for the 13 non-R-J5 axes."""
import argparse
import json
from pathlib import Path

import numpy as np


def stats(values):
    a = np.asarray(values, dtype=float)
    return {"count": int(a.size), "mae_rad": float(np.mean(abs(a))),
            "max_abs_rad": float(np.max(abs(a))), "mean_rad": float(np.mean(a))}


def summarize(path, tolerance):
    record = json.loads(path.read_text(encoding="utf-8"))
    runs = [r for r in record.get("waypoint_runs", [])
            if r.get("final_real_rad") is not None and r.get("final_sim_rad") is not None]
    expected = 15 if record.get("joint", "").endswith("joint4") else 18
    if not runs:
        return {"joint": record.get("joint"), "status": "invalid", "reason": "no_complete_runs"}
    raw = [r["final_real_rad"] - r["target_rad"] for r in runs]
    emulated = [r["final_sim_rad"] - r["final_real_rad"] for r in runs]
    tracking = [r["sim_error_rad"] for r in runs if r.get("sim_error_rad") is not None]
    raw_s, emu_s, track_s = stats(raw), stats(emulated), stats(tracking)
    gates = {
        "recorder_passed": bool(record.get("passed")),
        "all_waypoints_complete": len(runs) == expected,
        "all_receipts_present": all(r.get("accepted_receipts", 0) >= 2 for r in runs),
        "sim_tracking_within_tolerance": track_s["max_abs_rad"] <= tolerance,
        "emulated_mae_no_worse_than_raw": emu_s["mae_rad"] <= raw_s["mae_rad"],
        "emulated_max_abs_screening": emu_s["max_abs_rad"] <= tolerance,
    }
    return {"joint": record.get("joint"), "status": "independent_session_validated" if all(gates.values()) else "not_promoted",
            "sample_count": len(runs), "raw_nominal_minus_real": raw_s,
            "emulated_sim_minus_real": emu_s, "sim_tracking": track_s, "gates": gates}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--tolerance-rad", type=float, default=0.01)
    args = p.parse_args()
    files = sorted(args.input_dir.glob("openarm_*_joint*.json"))
    rows = [summarize(f, args.tolerance_rad) for f in files]
    result = {"kind": "openarm_static_independent_remaining13_summary", "input_dir": str(args.input_dir),
              "frozen_calibration": "openarm_isaac_replay_calibration_v4_candidate_right_j5.json",
              "joint_count": len(rows), "promoted_joint_count": sum(r["status"] == "independent_session_validated" for r in rows),
              "joints": rows}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
