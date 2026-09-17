#!/usr/bin/env python3
"""Create an evidence ledger for scale-like static replay terms, offline only."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "calibrations/openarm_isaac_replay_calibration_v4_candidate_right_j5.json"
MAPPING = ROOT / "openarm_isaacsim_joint_map.json"
URDF = ROOT / "isaacsim_assets/openarm_v20_import/openarm_v20_isaac.urdf"
OUT = ROOT / "results/mapping_audit_v1/scale_mapping_audit_ledger.json"
THRESHOLD = 0.02


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    joints = {item.attrib["name"]: item for item in ET.parse(URDF).getroot().findall("joint")}
    records = []
    for name, entry in config["joints"].items():
        a = entry["emulation"]["a"]
        if abs(a - 1.0) < THRESHOLD:
            continue
        urdf = joints.get(name)
        axis = urdf.find("axis") if urdf is not None else None
        limit = urdf.find("limit") if urdf is not None else None
        records.append({
            "joint": name,
            "a": a,
            "deviation_from_one": a - 1.0,
            "classification": entry.get("classification", []),
            "name_mapping": {
                "real": mapping["canonical_to_real"].get(name),
                "sim": mapping["canonical_to_sim"].get(name),
                "matches_canonical": mapping["canonical_to_real"].get(name) == name and mapping["canonical_to_sim"].get(name) == name,
            },
            "urdf": {
                "present": urdf is not None,
                "type": None if urdf is None else urdf.attrib.get("type"),
                "axis_xyz": None if axis is None else axis.attrib.get("xyz"),
                "lower": None if limit is None else limit.attrib.get("lower"),
                "upper": None if limit is None else limit.attrib.get("upper"),
            },
            "audit_status": "partial_offline",
            "remaining_evidence": [
                "Isaac live DOF name/index and USD drive target units",
                "real controller profile, encoder convention, and transmission ratio",
                "physical positive-direction and limit verification",
            ],
        })
    result = {
        "kind": "openarm_scale_mapping_audit_ledger",
        "scope": "offline name/URDF audit only; no simulator or real command",
        "calibration": str(CONFIG),
        "scale_threshold_abs_a_minus_one": THRESHOLD,
        "candidate_joint_count": len(records),
        "records": records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
