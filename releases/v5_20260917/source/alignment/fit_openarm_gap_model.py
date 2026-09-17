#!/usr/bin/env python3
"""Fit explainable Sim2Real gap candidates from settled OpenArm trials.

This is deliberately an offline, compare/replay-layer tool.  It never sends a
ROS message and never changes USD, URDF, Isaac drive parameters, or hardware
commands.  A candidate is only eligible for replay validation after the input
trial has valid paired final states.
"""
import argparse
import glob
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


def _median(values):
    return float(np.median(values)) if values else None


def _std(values):
    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def _direction(previous_target, target, tolerance=1e-9):
    delta = target - previous_target
    if delta > tolerance:
        return "positive"
    if delta < -tolerance:
        return "negative"
    return "hold"


def _rows_from_file(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not data.get("passed") or data.get("aborted"):
        return [], {"path": path, "reason": "trial_not_valid"}
    rows = []
    previous_by_repetition = {}
    for run in data.get("waypoint_runs", []):
        real, sim = run.get("final_real_rad"), run.get("final_sim_rad")
        target = run.get("target_rad")
        repetition = run.get("repetition")
        if real is None or sim is None or target is None:
            continue
        previous = previous_by_repetition.get(repetition, target)
        rows.append({
            "source": path,
            "repetition": repetition,
            "relative_target_rad": run.get("relative_target_rad"),
            "target_rad": float(target),
            "q_real_rad": float(real),
            "q_sim_rad": float(sim),
            "gap_rad": float(real) - float(sim),
            "approach_direction": _direction(previous, float(target)),
        })
        previous_by_repetition[repetition] = float(target)
    return rows, None


def _fit_joint(joint, rows, args):
    q_sim = np.asarray([r["q_sim_rad"] for r in rows], dtype=float)
    q_real = np.asarray([r["q_real_rad"] for r in rows], dtype=float)
    directions = [r["approach_direction"] for r in rows]
    positive = np.asarray([d == "positive" for d in directions], dtype=float)
    negative = np.asarray([d == "negative" for d in directions], dtype=float)

    # q_real = a*q_sim + b + h_pos I(pos) + h_neg I(neg).
    # Hold samples establish the common intercept.  If holds are absent, the
    # direction coefficients remain underdetermined and are reported as such.
    design = np.column_stack([q_sim, np.ones(len(rows)), positive, negative])
    coefficients, _, rank, _ = np.linalg.lstsq(design, q_real, rcond=None)
    a, b, h_positive, h_negative = [float(x) for x in coefficients]
    predicted = design @ coefficients
    residuals = (q_real - predicted).tolist()
    gaps = [r["gap_rad"] for r in rows]
    distinct_targets = sorted({round(r["q_sim_rad"], 5) for r in rows})
    pos_gaps = [r["gap_rad"] for r in rows if r["approach_direction"] == "positive"]
    neg_gaps = [r["gap_rad"] for r in rows if r["approach_direction"] == "negative"]
    hold_gaps = [r["gap_rad"] for r in rows if r["approach_direction"] == "hold"]
    direction_delta = None
    if pos_gaps and neg_gaps:
        direction_delta = _median(pos_gaps) - _median(neg_gaps)

    static_supported = (
        len(rows) >= args.min_samples and len(distinct_targets) >= 3
        and _std(gaps) <= args.static_spread_threshold_rad
    )
    scale_supported = (
        len(rows) >= args.min_samples and len(distinct_targets) >= 3
        and abs(a - 1.0) >= args.scale_threshold
    )
    directional_supported = (
        len(pos_gaps) >= args.min_direction_samples
        and len(neg_gaps) >= args.min_direction_samples
        and direction_delta is not None
        and abs(direction_delta) >= args.direction_threshold_rad
    )
    random_supported = (
        len(rows) >= args.min_samples
        and _std(residuals) >= args.noise_threshold_rad
    )
    classifications = []
    if static_supported:
        classifications.append("static_offset_candidate")
    if scale_supported:
        classifications.append("scale_or_transmission_candidate")
    if directional_supported:
        classifications.append("directional_backlash_or_friction_candidate")
    if random_supported:
        classifications.append("random_noise_or_unmodelled_state_candidate")
    if not classifications:
        classifications.append("insufficient_or_mixed_evidence")

    remediation = []
    if static_supported:
        remediation.append({
            "layer": "compare_or_replay",
            "action": "Use q_sim_corrected = a*q_sim + b only in a versioned replay/compare transform; validate on held-out repetitions.",
        })
    if scale_supported:
        remediation.append({
            "layer": "Isaac_mapping_review",
            "action": "Audit radians/degrees, joint axis sign, transmission ratio, drive target units, and joint limits. Do not edit USD/URDF until replay validation passes.",
        })
    if directional_supported:
        remediation.append({
            "layer": "stateful_replay_or_control_model",
            "action": "Keep separate positive/negative approach corrections; model friction/deadband/backlash in the Isaac control wrapper or randomization, not as a single URDF zero offset.",
        })
    if random_supported:
        remediation.append({
            "layer": "domain_randomization_and_policy_robustness",
            "action": "Estimate residual spread and randomize damping, friction, latency, observation noise, and load within measured bounds. Do not apply a deterministic offset for this component.",
        })
    remediation.append({
        "layer": "dynamic_delay",
        "action": "Not identifiable from settled endpoints alone. Fit command-to-response timing from timestamped ramps, then emulate command/observation delay with buffers and matching control rate in Isaac.",
    })

    return {
        "joint": joint,
        "usable_samples": len(rows),
        "distinct_sim_positions": distinct_targets,
        "fit": {
            "model": "q_real = a*q_sim + b + h_positive*I(positive) + h_negative*I(negative)",
            "rank": int(rank),
            "a": a,
            "b_rad": b,
            "h_positive_rad": h_positive,
            "h_negative_rad": h_negative,
            "residual_std_rad": _std(residuals),
        },
        "evidence": {
            "gap_median_rad": _median(gaps),
            "gap_std_rad": _std(gaps),
            "positive_gap_median_rad": _median(pos_gaps),
            "negative_gap_median_rad": _median(neg_gaps),
            "hold_gap_median_rad": _median(hold_gaps),
            "positive_minus_negative_gap_rad": direction_delta,
            "positive_samples": len(pos_gaps),
            "negative_samples": len(neg_gaps),
            "hold_samples": len(hold_gaps),
        },
        "classification": classifications,
        "delay": {
            "status": "not_identified_from_settled_endpoints",
            "required_measurement": "timestamped ramps or steps with response onset and t90/t95 windows",
        },
        "Isaac_candidate_remediation": remediation,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-glob", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-samples", type=int, default=9)
    parser.add_argument("--min-direction-samples", type=int, default=3)
    parser.add_argument("--static-spread-threshold-rad", type=float, default=0.005)
    parser.add_argument("--scale-threshold", type=float, default=0.03)
    parser.add_argument("--direction-threshold-rad", type=float, default=0.01)
    parser.add_argument("--noise-threshold-rad", type=float, default=0.005)
    args = parser.parse_args()

    grouped, rejected = defaultdict(list), []
    for path in sorted(glob.glob(args.input_glob)):
        rows, reason = _rows_from_file(path)
        if reason:
            rejected.append(reason)
        elif rows:
            grouped[rows[0]["source"] and json.loads(Path(path).read_text(encoding="utf-8"))["joint"]].extend(rows)
        else:
            rejected.append({"path": path, "reason": "no_paired_settled_samples"})
    if not grouped:
        raise SystemExit("no valid paired settled samples")
    report = {
        "schema_version": 1,
        "kind": "openarm_sim2real_gap_model_candidates",
        "safety": "offline candidates only; no USD, URDF, Isaac drive, or real-command mutation was performed",
        "joints": [_fit_joint(joint, rows, args) for joint, rows in sorted(grouped.items())],
        "rejected_inputs": rejected,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"joint_count": len(report["joints"]), "rejected_input_count": len(rejected)}, indent=2))


if __name__ == "__main__":
    main()
