#!/usr/bin/env python3
"""Reject promotion of an OpenArm dynamic correction without valid runtime evidence.

This is offline-only.  It never publishes ROS messages or modifies a USD.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--realtime-probe", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--minimum-rtf", type=float, default=0.95)
    args = parser.parse_args()
    rtf = json.loads(args.realtime_probe.read_text(encoding="utf-8"))
    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    factor = rtf.get("physics_realtime_factor")
    physics = analysis.get("physics_time_aggregate", {})
    reasons = []
    if not isinstance(factor, (int, float)) or factor < args.minimum_rtf:
        reasons.append("physics_realtime_factor_below_threshold")
    if physics.get("valid_step_count", 0) < 8:
        reasons.append("insufficient_physics_time_paired_steps")
    if physics.get("real_minus_isaac_physics_t90_s_mean") is None:
        reasons.append("missing_physics_time_t90")
    result = {
        "kind": "openarm_dynamic_correction_promotion_gate",
        "passed": not reasons,
        "physics_realtime_factor": factor,
        "minimum_rtf": args.minimum_rtf,
        "physics_time_valid_step_count": physics.get("valid_step_count"),
        "reasons": reasons,
        "next_action": ("candidate may enter isolated Isaac-only validation"
                        if not reasons else
                        "do not tune or persist dynamic parameters; repair runtime evidence first"),
    }
    print(json.dumps(result, indent=2))
    return 0 if not reasons else 2


if __name__ == "__main__":
    raise SystemExit(main())
