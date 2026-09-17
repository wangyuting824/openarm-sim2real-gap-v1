#!/usr/bin/env python3
"""Build a reviewable Isaac compare/replay compensation artifact.

This utility is deliberately offline.  It converts the interpretable fit from
``fit_openarm_gap_model.py`` into a configuration used to emulate the measured
real joint response in Isaac replay:

    q_emulated = a * q_nominal + b + h(direction)

It never sends ROS messages and never modifies USD, URDF, Isaac drives, or the
real controller.  The inverse relation is recorded for a future, separately
approved real-command study only; it is disabled in the generated artifact.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _mode(classifications):
    items = set(classifications)
    if "random_noise_or_unmodelled_state_candidate" in items:
        return "domain_randomization_candidate"
    if "scale_or_transmission_candidate" in items:
        return "mapping_audit_then_replay_candidate"
    if "directional_backlash_or_friction_candidate" in items:
        return "stateful_directional_replay_candidate"
    if "static_offset_candidate" in items:
        return "static_compare_replay_candidate"
    return "not_eligible"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = Path(args.candidates)
    report = json.loads(source.read_text(encoding="utf-8"))
    joints = {}
    for item in report["joints"]:
        fit = item["fit"]
        if fit["a"] == 0.0:
            raise ValueError("zero scale for " + item["joint"])
        joints[item["joint"]] = {
            "status": "candidate_requires_heldout_replay",
            "application_mode": _mode(item["classification"]),
            "classification": item["classification"],
            "emulation": {
                "formula": "q_emulated_rad = a*q_nominal_rad + b_rad + h(direction)",
                "a": fit["a"],
                "b_rad": fit["b_rad"],
                "h_positive_rad": fit["h_positive_rad"],
                "h_negative_rad": fit["h_negative_rad"],
                "h_hold_rad": 0.0,
                "residual_std_rad": fit["residual_std_rad"],
            },
            "inverse_real_command": {
                "formula": "q_command_candidate_rad = (q_goal_rad - b_rad - h(direction))/a",
                "enabled": False,
                "reason": "requires separate real-command authorization and held-out replay validation",
            },
            "delay": item["delay"],
        }

    artifact = {
        "schema_version": 1,
        "kind": "openarm_isaac_compare_replay_compensation_candidates",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_candidates": str(source),
        "source_model": "q_real = a*q_sim + b + h_positive*I(positive) + h_negative*I(negative)",
        "default_enabled": False,
        "scope": "Isaac compare/replay only; no live real command, USD, URDF, or drive mutation",
        "usage": {
            "direction": "compare each named joint target with its previous target; use positive, negative, or hold",
            "ordering": ["canonical nominal target", "stateful emulation transform", "Isaac replay/compare metric"],
            "required_before_enable": [
                "independent held-out paired replay per joint",
                "mapping audit for every scale_or_transmission_candidate",
                "timestamped dynamic trial before any delay value is added",
            ],
        },
        "joints": joints,
        "excluded_joints": [
            {
                "joint": "openarm_right_joint6",
                "reason": "source trial_not_valid; no compensation may be inferred",
            },
            {
                "joint": "openarm_right_joint7",
                "reason": "not measured in v3; no compensation may be inferred",
            },
        ],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "candidate_joint_count": len(joints),
                      "excluded_joint_count": len(artifact["excluded_joints"])}, indent=2))


if __name__ == "__main__":
    main()
