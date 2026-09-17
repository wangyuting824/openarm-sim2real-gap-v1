#!/usr/bin/env python3
"""Fit candidate no-load finger-joint to opening-width models from one scan."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def linear_fit(points):
    n = len(points)
    xbar = sum(x for x, _ in points) / n
    ybar = sum(y for _, y in points) / n
    denom = sum((x - xbar) ** 2 for x, _ in points)
    if denom == 0:
        raise ValueError("cannot fit a constant command")
    a = sum((x - xbar) * (y - ybar) for x, y in points) / denom
    return a, ybar - a * xbar


def metrics(points, a, b):
    errors = [y - (a * x + b) for x, y in points]
    return {"mae_mm": sum(abs(e) for e in errors) / len(errors), "max_abs_error_mm": max(abs(e) for e in errors)}


def one_side(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    readings = [r for r in data.get("readings", []) if r.get("measured_opening_mm") is not None]
    if len(readings) < 8:
        raise ValueError(f"insufficient caliper readings in {path}")
    outcome = {"side": data["side"], "joint": data["joint"], "directions": {}}
    for direction in ("increasing", "decreasing"):
        rows = [r for r in readings if r["direction"] == direction]
        # 0.40 rad is deliberately retained as a middle-width holdout point.
        held = [r for r in rows if math.isclose(abs(r["command_rad"]), 0.40, abs_tol=1e-8)]
        train = [r for r in rows if r not in held]
        if len(train) < 3 or len(held) != 1:
            raise ValueError(f"missing train/held-out design for {data['side']} {direction}")
        train_pts = [(r["command_rad"], r["measured_opening_mm"]) for r in train]
        a, b = linear_fit(train_pts)
        held_row = held[0]
        held_error = held_row["measured_opening_mm"] - (a * held_row["command_rad"] + b)
        outcome["directions"][direction] = {
            "candidate_model": {"opening_mm": "a * q_rad + b", "a_mm_per_rad": a, "b_mm": b},
            "training_metrics": metrics(train_pts, a, b),
            "held_out": {"command_rad": held_row["command_rad"], "opening_mm": held_row["measured_opening_mm"], "error_mm": held_error},
        }
    increasing = {r["command_rad"]: r["measured_opening_mm"] for r in readings if r["direction"] == "increasing"}
    decreasing = {r["command_rad"]: r["measured_opening_mm"] for r in readings if r["direction"] == "decreasing"}
    common = sorted(set(increasing) & set(decreasing))
    outcome["return_gap_mm"] = {str(q): increasing[q] - decreasing[q] for q in common}
    outcome["status"] = "gripper_kinematic_candidate"
    return outcome


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = {"schema_version": 1, "kind": "openarm_gripper_kinematic_scan_summary", "status": "gripper_kinematic_candidate",
              "sides": [one_side(args.input_dir / "left.json"), one_side(args.input_dir / "right.json")],
              "promotion": "A task opening tolerance must be declared before this candidate can be accepted."}
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
