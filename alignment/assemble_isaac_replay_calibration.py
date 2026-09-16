#!/usr/bin/env python3
# Assemble importable Isaac replay calibration from one or more candidate files.
# Offline only: this utility never imports ROS or changes a simulator.
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def mode(classification):
    kinds = set(classification)
    if "scale_or_transmission_candidate" in kinds:
        return "mapping_audit_then_stateful_replay"
    if "directional_backlash_or_friction_candidate" in kinds:
        return "stateful_directional_replay"
    return "static_compare_replay"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--provisional-joint", action="append", default=[])
    parser.add_argument("--override-joint", action="append", default=[], help="Permit a later candidate file to replace this named joint.")
    args = parser.parse_args()
    provisional = set(args.provisional_joint)
    overrides = set(args.override_joint)
    joints, sources, replacements = {}, [], []
    for source_name in args.candidate:
        source = Path(source_name)
        report = json.loads(source.read_text(encoding="utf-8"))
        sources.append(str(source))
        for item in report["joints"]:
            name = item["joint"]
            if name in joints and name not in overrides:
                raise ValueError("duplicate joint: " + name)
            if name in joints:
                replacements.append({"joint": name, "replaced_by": str(source)})
            fit = item["fit"]
            joints[name] = {
                "status": ("provisional_requires_independent_real_replay" if name in provisional
                           else "isaac_replay_candidate"),
                "enabled_for_isaac_replay": name not in provisional,
                "application_mode": mode(item["classification"]),
                "classification": item["classification"],
                "emulation": {
                    "formula": "q_emulated_rad = a*q_nominal_rad + b_rad + h(direction)",
                    "a": fit["a"], "b_rad": fit["b_rad"],
                    "h_positive_rad": fit["h_positive_rad"],
                    "h_negative_rad": fit["h_negative_rad"],
                    "h_hold_rad": 0.0,
                    "residual_std_rad": fit["residual_std_rad"],
                },
                "delay": item["delay"],
            }
    artifact = {
        "schema_version": 2,
        "kind": "openarm_isaac_replay_calibration",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_candidate_files": sources,
        "replacements": replacements,
        "scope": "Isaac compare/replay only; never a real-command transform",
        "default_enabled": False,
        "joint_count": len(joints),
        "enabled_joint_count": sum(x["enabled_for_isaac_replay"] for x in joints.values()),
        "provisional_joint_count": sum(not x["enabled_for_isaac_replay"] for x in joints.values()),
        "joints": joints,
        "import_contract": {
            "input": "named canonical nominal joint targets in radians",
            "output": "named Isaac replay targets in radians",
            "direction": "positive/negative/hold from each joint's previous nominal target",
            "limits": "apply the existing named-joint mechanical limit guard after this transform",
            "exclusions": "a disabled provisional joint passes through unchanged",
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "joint_count": artifact["joint_count"],
                      "enabled_joint_count": artifact["enabled_joint_count"],
                      "provisional_joint_count": artifact["provisional_joint_count"]}, indent=2))


if __name__ == "__main__":
    main()
