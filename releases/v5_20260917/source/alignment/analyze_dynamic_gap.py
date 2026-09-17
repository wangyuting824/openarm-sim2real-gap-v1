#!/usr/bin/env python3
"""Analyze paired OpenArm dynamic-step recordings without commanding ROS."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path


def median(values):
    return statistics.median(values) if values else None


def stdev(values):
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def window(samples, begin, end):
    return [x["position_rad"] for x in samples if begin <= x["t_monotonic"] < end]


def first_crossing(samples, start, threshold, positive):
    for sample in samples:
        if sample["t_monotonic"] < start:
            continue
        if (positive and sample["position_rad"] >= threshold) or (not positive and sample["position_rad"] <= threshold):
            return sample["t_monotonic"] - start
    return None


def endpoint_metrics(samples, event, previous_event):
    receipt = event["accepted_receipt_t_monotonic"]
    pre_start = previous_event["accepted_receipt_t_monotonic"] if previous_event else receipt - 0.5
    pre = window(samples, max(pre_start, receipt - 0.5), receipt)
    post = window(samples, receipt + event["hold_s"] * 0.5, receipt + event["hold_s"])
    q0, qinf = median(pre), median(post)
    result = {"valid": False, "q0_rad": q0, "qinf_rad": qinf, "pre_noise_std_rad": stdev(pre)}
    if q0 is None or qinf is None:
        result["reason"] = "missing_pre_or_steady_window"
        return result
    delta = qinf - q0
    if abs(delta) < 0.002:
        result["reason"] = "response_below_minimum_amplitude"
        return result
    positive = delta > 0
    onset_delta = max(3 * result["pre_noise_std_rad"], 0.05 * abs(delta))
    onset = first_crossing(samples, receipt, q0 + (onset_delta if positive else -onset_delta), positive)
    metrics = {"valid": onset is not None, "q0_rad": q0, "qinf_rad": qinf,
               "response_amplitude_rad": delta, "pre_noise_std_rad": result["pre_noise_std_rad"],
               "onset_s": onset}
    for fraction in (0.1, 0.5, 0.9, 0.95):
        metrics["t%d_s" % round(fraction * 100)] = first_crossing(samples, receipt, q0 + fraction * delta, positive)
    values = window(samples, receipt, receipt + event["hold_s"])
    if values:
        peak = max(values) if positive else min(values)
        metrics["overshoot_rad"] = (peak - qinf) if positive else (qinf - peak)
    return metrics


def isaac_physics_time_metrics(sim_samples, event, metrics, timing_records):
    """Report response time in accumulated actual PhysX seconds when available.

    Wall-clock response time remains the transfer-relevant end-to-end measure.
    PhysX time reveals whether a low simulation real-time factor is inflating
    that wall-clock result.  It is deliberately diagnostic-only and never
    mixed into real-minus-Isaac delay inference.
    """
    source_stamp = event.get("published_ros_stamp_ns")
    records = [r for r in timing_records
               if r.get("source_command_stamp_ns") == source_stamp and
               r.get("target_applied_physics_s") is not None]
    if not records or not metrics.get("valid"):
        return {"available": False,
                "reason": "missing_target_applied_physics_timestamp"}
    start = records[-1]["target_applied_physics_s"]
    q0, qinf = metrics["q0_rad"], metrics["qinf_rad"]
    delta = qinf - q0
    positive = delta > 0
    result = {"available": True, "target_applied_physics_s": start}
    for fraction in (0.05, 0.1, 0.5, 0.9, 0.95):
        threshold = q0 + fraction * delta
        crossed = next((sample for sample in sim_samples
                        if sample.get("physics_time_s") is not None and
                        sample["physics_time_s"] >= start and
                        ((positive and sample["position_rad"] >= threshold) or
                         (not positive and sample["position_rad"] <= threshold))), None)
        result["t%d_s" % round(fraction * 100)] = (
            crossed["physics_time_s"] - start if crossed is not None else None)
    if result.get("t90_s") is not None and metrics.get("t90_s"):
        result["wall_over_physics_t90_ratio"] = metrics["t90_s"] / result["t90_s"]
    return result


def classify(real, sim):
    if not real.get("valid") or not sim.get("valid"):
        return "invalid_or_unsettled"
    onset = real["onset_s"] - sim["onset_s"]
    t90 = real["t90_s"] - sim["t90_s"] if real.get("t90_s") is not None and sim.get("t90_s") is not None else None
    if t90 is None:
        return "insufficient_t90"
    if abs(onset - t90) <= 0.04 and abs(onset) >= 0.04:
        return "constant_delay_candidate"
    if abs(t90 - onset) >= 0.04:
        return "bandwidth_or_rate_limit_candidate"
    return "dynamically_matched_within_resolution"


def paired_summary(records):
    valid = [x for x in records if x["kind"] == "step" and x["real"].get("valid") and x["sim"].get("valid")]
    onset = [x["real"]["onset_s"] - x["sim"]["onset_s"] for x in valid]
    t90 = [x["real"]["t90_s"] - x["sim"]["t90_s"] for x in valid
           if x["real"].get("t90_s") is not None and x["sim"].get("t90_s") is not None]
    return {
        "valid_step_count": len(valid),
        "real_minus_isaac_onset_s_mean": (sum(onset) / len(onset)) if onset else None,
        "real_minus_isaac_onset_s_std": stdev(onset),
        "real_minus_isaac_t90_s_mean": (sum(t90) / len(t90)) if t90 else None,
        "real_minus_isaac_t90_s_std": stdev(t90),
    }


def paired_physics_time_summary(records):
    """Compare real elapsed time with Isaac's actual accumulated PhysX time.

    Real joint feedback is physical wall time; Isaac samples are stamped with
    accumulated physics dt.  This pairing identifies the model response while
    remaining independent of GUI/render slow-down.  It must not be promoted
    while the separate real-time-factor gate is failing.
    """
    valid = [x for x in records if x["kind"] == "step" and x["real"].get("valid") and
             x["sim_physics_time"].get("available")]
    onset = [x["real"]["onset_s"] - x["sim_physics_time"]["t5_s"]
             for x in valid if x["real"].get("onset_s") is not None and
             x["sim_physics_time"].get("t5_s") is not None]
    t90 = [x["real"]["t90_s"] - x["sim_physics_time"]["t90_s"]
           for x in valid if x["real"].get("t90_s") is not None and
           x["sim_physics_time"].get("t90_s") is not None]
    return {
        "valid_step_count": len(valid),
        "real_minus_isaac_physics_onset_s_mean": (sum(onset) / len(onset)) if onset else None,
        "real_minus_isaac_physics_onset_s_std": stdev(onset),
        "real_minus_isaac_physics_t90_s_mean": (sum(t90) / len(t90)) if t90 else None,
        "real_minus_isaac_physics_t90_s_std": stdev(t90),
    }


def candidate_from_physics_training(training, holdout):
    """Classify a correction only from actual PhysX-time response metrics."""
    onset = training["real_minus_isaac_physics_onset_s_mean"]
    t90 = training["real_minus_isaac_physics_t90_s_mean"]
    if training["valid_step_count"] < 8 or onset is None or t90 is None:
        return {"status": "not_identified", "reason": "insufficient_two-repetition paired steps"}
    if abs(onset - t90) <= 0.04 and abs(onset) >= 0.04:
        kind = "constant_delay_candidate"
        action = "Isaac-only command or observation FIFO candidate; never block a bridge callback."
    elif abs(t90 - onset) >= 0.04:
        kind = "bandwidth_or_rate_limit_candidate"
        if t90 < 0:
            action = ("Isaac is slower than real: run a simulator-only drive/control-rate/velocity-limit tuning study; "
                      "do not add a delay FIFO and do not modify a persistent USD drive before validation.")
        else:
            action = ("Isaac is faster than real: test a bounded Isaac command/observation buffer or matched rate/limit model "
                      "in simulator-only replay.")
    else:
        kind = "dynamically_matched_within_resolution"
        action = "No deterministic dynamic correction candidate; retain measured jitter for randomization."
    h_t90 = holdout["real_minus_isaac_physics_t90_s_mean"]
    h_onset = holdout["real_minus_isaac_physics_onset_s_mean"]
    stable = (h_t90 is not None and h_onset is not None and
              abs(h_t90 - t90) <= 0.10 and abs(h_onset - onset) <= 0.10)
    return {
        "status": "within_session_candidate" if stable else "holdout_not_confirmed",
        "classification": kind,
        "training_repetitions": [1, 2],
        "within_session_holdout_repetition": 3,
        "holdout_consistent_with_training": stable,
        "isaac_only_next_action": action,
        "promotion": "require different-amplitude/ramp and independent powered-session validation",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    events = raw["events"]
    records = []
    previous = None
    for index, event in enumerate(events):
        real = endpoint_metrics(raw.get("real_samples", []), event, previous)
        sim = endpoint_metrics(raw.get("sim_samples", []), event, previous)
        sim_physics_time = isaac_physics_time_metrics(raw.get("sim_samples", []), event, sim,
                                                       raw.get("isaac_timing", []))
        records.append({"index": index, **event, "real": real, "sim": sim,
                        "sim_physics_time": sim_physics_time,
                        "classification": classify(real, sim)})
        previous = event
    valid_steps = [x for x in records if x["kind"] == "step" and x["real"].get("valid") and x["sim"].get("valid")]
    sim_only_steps = [x for x in records if x["kind"] == "step" and x["sim"].get("valid")]
    paired = paired_summary(records)
    paired_physics = paired_physics_time_summary(records)
    training = paired_summary([x for x in records if x["repetition"] in (1, 2)])
    holdout = paired_summary([x for x in records if x["repetition"] == 3])
    physics_training = paired_physics_time_summary(
        [x for x in records if x["repetition"] in (1, 2)])
    physics_holdout = paired_physics_time_summary(
        [x for x in records if x["repetition"] == 3])
    result = {
        "schema_version": 1, "kind": "openarm_real_sim_dynamic_gap_analysis",
        "source": str(args.input), "joint": raw["joint"],
        "static_replay_during_capture": raw.get("static_replay_required"),
        "fit_repetitions": [1, 2], "within_session_holdout_repetition": 3,
        "step_records": records,
        "aggregate": paired,
        "physics_time_aggregate": paired_physics,
        "training_summary": training,
        "within_session_holdout_summary": holdout,
        "physics_time_training_summary": physics_training,
        "physics_time_within_session_holdout_summary": physics_holdout,
        "wall_time_observation": {
            "status": "diagnostic_only",
            "reason": "wall-time response can be inflated by simulation real-time factor",
            "aggregate": paired,
        },
        "dynamic_candidate": candidate_from_physics_training(physics_training, physics_holdout),
        # This is deliberately separate from paired dynamic-gap evidence.  It
        # proves the Isaac route produces measurable step responses, but cannot
        # estimate a real-minus-Isaac dynamic term.
        "isaac_only_baseline": {
            "valid_step_count": len(sim_only_steps),
            "onset_s_mean": (sum(x["sim"]["onset_s"] for x in sim_only_steps) / len(sim_only_steps)) if sim_only_steps else None,
            "t90_s_mean": (sum(x["sim"]["t90_s"] for x in sim_only_steps if x["sim"].get("t90_s") is not None) /
                           len([x for x in sim_only_steps if x["sim"].get("t90_s") is not None])) if any(x["sim"].get("t90_s") is not None for x in sim_only_steps) else None,
            "interpretation": "simulator dynamic baseline only; no real dynamic gap is inferred",
        },
        "promotion": "candidate_only: require holdout, different amplitude/ramp, and independent session",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], indent=2))


if __name__ == "__main__":
    main()
