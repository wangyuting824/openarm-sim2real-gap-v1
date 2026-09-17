#!/usr/bin/env python3
"""Run an Isaac-only RTF probe with no interactive viewport.

Execute through Isaac Sim's ``python.sh`` on a host where no other Isaac/Kit
process is running.  The stage is opened unchanged; Replicator render products
already authored in that stage remain available, while the editor viewport is
absent.  No ROS command is published and no USD layer is saved.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--alignment-dir", type=Path,
                        default=Path("/home/tangyuan/openarm_ws/alignment"))
    parser.add_argument("--stage-load-timeout-s", type=float, default=45.0)
    parser.add_argument("--settle-s", type=float, default=3.0)
    parser.add_argument("--probe-wait-s", type=float, default=14.0)
    args = parser.parse_args()
    if not args.stage.is_file():
        raise FileNotFoundError(args.stage)

    try:
        from isaacsim import SimulationApp
    except ImportError:  # Isaac Sim 4.x compatibility for older deployment hosts.
        from omni.isaac.kit import SimulationApp

    app = SimulationApp({"headless": True})
    try:
        import omni.usd

        context = omni.usd.get_context()
        context.open_stage(str(args.stage))
        deadline = time.monotonic() + args.stage_load_timeout_s
        while context.get_stage() is None:
            if time.monotonic() >= deadline:
                raise TimeoutError("USD stage did not load: " + str(args.stage))
            app.update()

        def load(name: str) -> None:
            path = args.alignment_dir / name
            namespace = {"__file__": str(path), "__name__": "__main__"}
            exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)

        # The daemon queues state/bridge setup onto Kit updates.
        load("isaacsim_gap_control_daemon.py")
        settle_deadline = time.monotonic() + args.settle_s
        while time.monotonic() < settle_deadline:
            app.update()

        output = args.alignment_dir / "results" / "isaacsim_realtime_factor_probe.json"
        before = output.stat().st_mtime_ns if output.exists() else None
        load("isaacsim_measure_realtime_factor.py")
        deadline = time.monotonic() + args.probe_wait_s
        while time.monotonic() < deadline:
            app.update()
            if output.exists() and output.stat().st_mtime_ns != before:
                try:
                    result = json.loads(output.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                if result.get("kind") == "openarm_isaac_realtime_factor_probe":
                    print("OPENARM_HEADLESS_RTF=" + json.dumps(result, separators=(",", ":")))
                    return 0
        raise TimeoutError("headless realtime-factor probe did not produce a new result")
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
