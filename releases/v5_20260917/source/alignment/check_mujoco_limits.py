#!/usr/bin/env python3
"""Scan MuJoCo joint limits without KER, controllers, or hardware motion.

The script only sets qpos in a local MuJoCo model and calls mj_forward.  It
does not start the viewer, publish commands, or connect to a robot.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import mujoco


def read_mechanical_limits(path: Path) -> dict[str, tuple[float, float, str]]:
    result = {}
    if not path.is_file():
        return result
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                result[row["joint"]] = (
                    float(row["lower_rad"]), float(row["upper_rad"]),
                    row.get("source_type", "unspecified"),
                )
            except (KeyError, TypeError, ValueError):
                continue
    return result


def scan(xml: Path, mechanical: dict[str, tuple[float, float]]) -> list[dict[str, object]]:
    model = mujoco.MjModel.from_xml_path(str(xml))
    data = mujoco.MjData(model)
    rows = []
    for joint_id in range(model.njnt):
        if model.jnt_type[joint_id] != mujoco.mjtJoint.mjJNT_HINGE:
            continue
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id)
        qpos_addr = model.jnt_qposadr[joint_id]
        sim_lower, sim_upper = map(float, model.jnt_range[joint_id])
        ctrl_lower = ctrl_upper = math.nan
        if model.jnt_dofadr[joint_id] < model.nu:
            # Actuator assignment is not guaranteed to follow joint order;
            # report the joint range as the authoritative position boundary.
            pass
        data.qpos[qpos_addr] = sim_lower
        mujoco.mj_forward(model, data)
        data.qpos[qpos_addr] = (sim_lower + sim_upper) / 2.0
        mujoco.mj_forward(model, data)
        data.qpos[qpos_addr] = sim_upper
        mujoco.mj_forward(model, data)
        mech_lower, mech_upper, source_type = mechanical.get(name, (math.nan, math.nan, ""))
        lower_ok = math.isfinite(mech_lower) and sim_lower >= mech_lower
        upper_ok = math.isfinite(mech_upper) and sim_upper <= mech_upper
        rows.append({
            "joint": name,
            "sim_lower_rad": sim_lower,
            "sim_upper_rad": sim_upper,
            "sim_lower_deg": math.degrees(sim_lower),
            "sim_upper_deg": math.degrees(sim_upper),
            "mechanical_lower_rad": mech_lower,
            "mechanical_upper_rad": mech_upper,
            "mechanical_source_type": source_type or "unknown",
            "lower_inside_mechanical": lower_ok if math.isfinite(mech_lower) else "unknown",
            "upper_inside_mechanical": upper_ok if math.isfinite(mech_upper) else "unknown",
            "status": (
                "NEEDS_MECHANICAL_LIMITS" if not mechanical.get(name)
                else ("PASS" if lower_ok and upper_ok and source_type == "measured_mechanical"
                      else ("REFERENCE_ONLY" if lower_ok and upper_ok else "FAIL"))
            ),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", type=Path, default=Path(
        "dora/dora-openarm-data-collection/.venv/share/openarm_mujoco/v2/cell/demo.xml"))
    parser.add_argument("--mechanical-csv", type=Path, default=Path("alignment/mechanical_limits.csv"))
    parser.add_argument("--output", type=Path, default=Path("alignment/results/mujoco_limit_scan.csv"))
    args = parser.parse_args()
    rows = scan(args.xml, read_mechanical_limits(args.mechanical_csv))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Scanned {len(rows)} hinge joints from {args.xml}")
    for row in rows:
        print(f"{row['joint']}: [{row['sim_lower_deg']:.3f}, {row['sim_upper_deg']:.3f}] deg -> {row['status']}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
