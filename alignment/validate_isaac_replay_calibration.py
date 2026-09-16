#!/usr/bin/env python3
"""Validate an importable Isaac compare/replay calibration artifact offline."""
import argparse
import json
import math
from pathlib import Path

from isaac_gap_compensation import CompensationModel


def finite(value, label):
    if not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    path = Path(args.config)
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 2:
        raise ValueError("expected schema_version=2")
    if config.get("kind") != "openarm_isaac_replay_calibration":
        raise ValueError("unexpected calibration kind")
    joints = config.get("joints")
    if not isinstance(joints, dict) or not joints:
        raise ValueError("joints must be a non-empty object keyed by canonical joint name")
    if config.get("joint_count") != len(joints):
        raise ValueError("joint_count does not match joints")

    enabled = []
    provisional = []
    for name, item in joints.items():
        if not name.startswith("openarm_"):
            raise ValueError(f"invalid canonical joint name: {name}")
        emulation = item.get("emulation", {})
        if emulation.get("formula") != "q_emulated_rad = a*q_nominal_rad + b_rad + h(direction)":
            raise ValueError(f"unexpected emulation formula for {name}")
        for key in ("a", "b_rad", "h_positive_rad", "h_negative_rad", "h_hold_rad", "residual_std_rad"):
            finite(emulation.get(key), f"{name}.{key}")
        if item.get("enabled_for_isaac_replay"):
            enabled.append(name)
        else:
            provisional.append(name)
    if config.get("enabled_joint_count") != len(enabled):
        raise ValueError("enabled_joint_count does not match joints")
    if config.get("provisional_joint_count") != len(provisional):
        raise ValueError("provisional_joint_count does not match joints")

    model = CompensationModel.from_path(path)
    probe = 0.02
    transformed = {name: model.emulate(name, probe) for name in enabled}
    passthrough = {name: model.emulate(name, probe) for name in provisional}
    for name, result in passthrough.items():
        if result["applied"] or abs(result["q_emulated_rad"] - probe) > 1e-12:
            raise ValueError(f"disabled provisional joint did not pass through: {name}")
    report = {
        "kind": "openarm_isaac_replay_calibration_validation",
        "config": str(path),
        "passed": True,
        "joint_count": len(joints),
        "enabled_joint_count": len(enabled),
        "provisional_joint_count": len(provisional),
        "enabled_probe_targets_rad": {name: value["q_emulated_rad"] for name, value in transformed.items()},
        "provisional_passthrough_targets_rad": {name: value["q_emulated_rad"] for name, value in passthrough.items()},
    }
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
