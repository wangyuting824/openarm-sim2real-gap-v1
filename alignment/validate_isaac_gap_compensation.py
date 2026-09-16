#!/usr/bin/env python3
"""Within-session hold-out validation for the offline gap transform.

For each joint, the largest repetition ID is held out.  The affine and
directional terms are fitted on the earlier repetitions and evaluated on the
held-out settled states.  This is replay evidence only, not authorization to
enable a runtime transform or change a real command.
"""
import argparse
import json
from pathlib import Path

import numpy as np


def _percentile(values, value):
    return float(np.percentile(np.abs(values), value)) if len(values) else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    results = []
    for item in source["joints"]:
        rows = item["rows"]
        repeats = sorted({row["repetition"] for row in rows})
        if len(repeats) < 2:
            continue
        holdout_id = repeats[-1]
        train = [row for row in rows if row["repetition"] != holdout_id]
        holdout = [row for row in rows if row["repetition"] == holdout_id]
        if not train or not holdout:
            continue
        def design(values):
            return np.asarray([[row["q_sim_rad"], 1.0,
                                float(row["approach_direction"] == "positive"),
                                float(row["approach_direction"] == "negative")]
                               for row in values], dtype=float)
        train_x, test_x = design(train), design(holdout)
        train_y = np.asarray([row["q_real_rad"] for row in train], dtype=float)
        test_y = np.asarray([row["q_real_rad"] for row in holdout], dtype=float)
        coefficients, _, rank, _ = np.linalg.lstsq(train_x, train_y, rcond=None)
        raw = test_y - np.asarray([row["q_sim_rad"] for row in holdout], dtype=float)
        corrected = test_y - test_x @ coefficients
        results.append({
            "joint": item["joint"],
            "holdout_repetition": holdout_id,
            "training_repetitions": repeats[:-1],
            "fit_rank": int(rank),
            "fit": {"a": float(coefficients[0]), "b_rad": float(coefficients[1]),
                    "h_positive_rad": float(coefficients[2]), "h_negative_rad": float(coefficients[3])},
            "raw": {"mae_rad": float(np.mean(np.abs(raw))), "p95_abs_rad": _percentile(raw, 95)},
            "emulated": {"mae_rad": float(np.mean(np.abs(corrected))), "p95_abs_rad": _percentile(corrected, 95)},
            "improves_holdout_mae": bool(np.mean(np.abs(corrected)) < np.mean(np.abs(raw))),
            "scope": "within-session held-out replay evidence only",
        })
    artifact = {
        "schema_version": 1,
        "kind": "openarm_isaac_gap_compensation_holdout_validation",
        "source_candidates": args.candidates,
        "scope": "offline only; does not enable compensation or mutate real/simulator systems",
        "joint_results": results,
        "excluded_joints": source.get("rejected_inputs", []),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"joint_count": len(results),
                      "improved_joint_count": sum(x["improves_holdout_mae"] for x in results)}, indent=2))


if __name__ == "__main__":
    main()
