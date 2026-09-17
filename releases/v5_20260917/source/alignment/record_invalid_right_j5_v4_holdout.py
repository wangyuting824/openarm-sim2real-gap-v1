#!/usr/bin/env python3
"""Record an incomplete R J5 v4 holdout without interpreting it as data."""
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("alignment/results/openarm_right_j5_v4_independent_power_holdout_v1/invalid_trial_record.json")
OUT.write_text(json.dumps({
    "kind": "openarm_right_j5_v4_independent_power_holdout_invalid_trial",
    "trial_id": "openarm_right_j5_v4_independent_power_holdout_v1",
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "invalid",
    "reason": "runner parent terminated before recorder wrote per-joint evidence; no completed return/receipt/state record",
    "actions_taken": [
        "stopped leftover enable_real router PID 2932774",
        "recorded post-abort read-only health evidence",
    ],
    "usable_for_calibration": False,
    "retry_requires": "new named single-use authorization",
}, indent=2) + "\n", encoding="utf-8")
print(OUT)
