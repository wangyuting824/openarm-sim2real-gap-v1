#!/usr/bin/env python3
"""Pure-Python, stateful OpenArm compare/replay compensation functions.

The module accepts only named joint positions.  It has no ROS or Isaac imports,
so it can be exercised before it is connected to an Isaac replay adapter.
"""
import argparse
import json
from pathlib import Path


class CompensationModel:
    def __init__(self, configuration):
        self.configuration = configuration
        self.previous_targets = {}

    @classmethod
    def from_path(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def emulate(self, joint, q_nominal_rad):
        entry = self.configuration["joints"].get(joint)
        if entry is None or not entry.get("enabled_for_isaac_replay", True):
            return {"joint": joint, "q_nominal_rad": q_nominal_rad,
                    "q_emulated_rad": q_nominal_rad, "direction": "unmodelled",
                    "applied": False}
        prior = self.previous_targets.get(joint)
        direction = "hold" if prior is None or q_nominal_rad == prior else (
            "positive" if q_nominal_rad > prior else "negative")
        values = entry["emulation"]
        h = values["h_%s_rad" % direction]
        q_emulated = values["a"] * q_nominal_rad + values["b_rad"] + h
        self.previous_targets[joint] = q_nominal_rad
        return {"joint": joint, "q_nominal_rad": q_nominal_rad,
                "q_emulated_rad": q_emulated, "direction": direction,
                "applied": True, "status": entry["status"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--joint", required=True)
    parser.add_argument("--targets-rad", required=True,
                        help="comma-separated nominal targets, evaluated in order")
    args = parser.parse_args()
    model = CompensationModel.from_path(args.config)
    rows = [model.emulate(args.joint, float(value))
            for value in args.targets_rad.split(",")]
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
