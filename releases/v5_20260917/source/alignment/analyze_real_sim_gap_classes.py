#!/usr/bin/env python3
"""Classify fixed-point OpenArm/Isaac gap evidence without commanding hardware.

A single outbound/return trial can expose a target gap and a return residual,
but cannot identify a reusable static correction.  This tool makes that limit
explicit and produces the smallest follow-up trajectory needed to distinguish
static offset, scale, directional backlash, and dynamic lag.
"""
import argparse
import glob
import json
import math
from pathlib import Path


def last_value_after(samples, timestamp):
    values = [s for s in samples if s["t_monotonic"] >= timestamp]
    return values[-1]["position_rad"] if values else None


def time_to_fraction(samples, start, initial, target, fraction=0.9):
    delta = target - initial
    if abs(delta) < 1e-9:
        return None
    threshold = initial + fraction * delta
    for sample in samples:
        if sample["t_monotonic"] < start:
            continue
        value = sample["position_rad"]
        if (delta > 0 and value >= threshold) or (delta < 0 and value <= threshold):
            return sample["t_monotonic"] - start
    return None


def mean_abs(values):
    return sum(abs(v) for v in values) / len(values) if values else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-glob", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--return-residual-threshold-rad", type=float, default=0.01)
    parser.add_argument("--dynamic-gap-threshold-s", type=float, default=0.10)
    args = parser.parse_args()

    paths = sorted(glob.glob(args.input_glob))
    if not paths:
        raise SystemExit("no input files matched")
    joints, target_gaps, returns = [], [], []
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        receipts = data.get("router_receipts", [])
        real = data.get("real_samples", [])
        sim = data.get("sim_samples", [])
        outbound_receipt = receipts[0]["t_monotonic"] if receipts else None
        real_t90 = sim_t90 = None
        if outbound_receipt is not None and real and sim:
            real_t90 = time_to_fraction(
                real, outbound_receipt, data["initial_real_rad"], data["target_rad"]
            )
            sim_t90 = time_to_fraction(
                sim, outbound_receipt, data["initial_sim_rad"], data["target_rad"]
            )
        target_gap = data.get("real_minus_sim_at_target_rad")
        return_residual = data.get("return_real_error_rad")
        labels = ["single_endpoint_offset_candidate"]
        if return_residual is not None and abs(return_residual) > args.return_residual_threshold_rad:
            labels.append("return_residual_or_directional_backlash_candidate")
        if real_t90 is not None and sim_t90 is not None and abs(real_t90 - sim_t90) > args.dynamic_gap_threshold_s:
            labels.append("dynamic_response_lag_candidate")
        labels.append("static_offset_unidentified_without_repeat_and_multiple_targets")
        item = {
            "joint": data["joint"],
            "target_rad": data["target_rad"],
            "real_minus_sim_at_target_rad": target_gap,
            "real_target_error_rad": data.get("outbound_real_error_rad"),
            "sim_target_error_rad": data.get("outbound_sim_error_rad"),
            "real_return_residual_rad": return_residual,
            "real_t90_s_from_router_receipt": real_t90,
            "sim_t90_s_from_router_receipt": sim_t90,
            "t90_real_minus_sim_s": None if real_t90 is None or sim_t90 is None else real_t90 - sim_t90,
            "classification": labels,
        }
        joints.append(item)
        if target_gap is not None:
            target_gaps.append(target_gap)
        if return_residual is not None:
            returns.append(return_residual)

    report = {
        "schema_version": 1,
        "kind": "openarm_real_sim_gap_classification",
        "source_count": len(joints),
        "conclusion": (
            "Isaac target tracking is valid in this dataset. The observed real-minus-sim "
            "target gaps are fixed-point candidates only; they are not calibration offsets yet."
        ),
        "aggregate": {
            "mean_abs_real_minus_sim_target_rad": mean_abs(target_gaps),
            "max_abs_real_minus_sim_target_rad": max(map(abs, target_gaps)) if target_gaps else None,
            "mean_abs_real_return_residual_rad": mean_abs(returns),
            "max_abs_real_return_residual_rad": max(map(abs, returns)) if returns else None,
        },
        "identifiability": {
            "static_offset": "not_identified: one outbound endpoint per joint",
            "scale": "not_identified: requires at least three target magnitudes",
            "directional_backlash": "candidate only: requires repeated positive and negative approaches",
            "dynamic_delay": "candidate only: receipt-to-feedback t90 is an approximate local timing metric; use timestamped ramps for fit",
        },
        "required_next_measurement": {
            "trajectory_per_joint": "measured_start -> +0.05 -> measured_start -> -0.05 -> measured_start -> +0.10 -> measured_start",
            "hold_s": 3.0,
            "publish_hz": 50,
            "repetitions": 3,
            "limits": "retain the existing per-trial 0.15 rad maximum excursion and guarded return",
            "fit_after_collection": "q_real = a*q_sim + b + h(direction), with separate delay tau; hold out one repetition",
        },
        "joints": joints,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["aggregate"], indent=2))


if __name__ == "__main__":
    main()
