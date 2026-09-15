# OpenArm Sim2Real Gap v1

This is the first reproducible release of the OpenArm + Isaac Sim Sim2Real
integration skill. It provides a guarded ROS 2 control route, Isaac-side
module recovery and drive repair, fixed-point baseline measurement, and
evidence from a completed real-plus-simulation 14-axis trial.

## Contents

- `skill/`: Codex Skill instructions and operating references.
- `alignment/`: ROS routers, measurement runners, Isaac Script Editor daemon,
  joint mapping, mechanical limits, and physical-trial manifests.
- `evidence/full14_v2_summary.json`: compact, shareable summary of the first
  accepted 14-axis real-plus-Isaac fixed-point baseline.
- `docs/`: integration ledger and Isaac measurement ledger.

## Validated v1 baseline

The `openarm_real_sim_bimanual_fixed_0p1_full14_v2` trial ran each left and
right arm joint sequentially at an absolute `0.1 rad` target, with a 50 Hz
three-second hold and return to its measured start. It recorded 28/28 accepted
target/return receipts. The Isaac position-drive repair allowed every arm axis
to track the simulator target within `0.01 rad`.

The real robot's mean absolute target error was `0.013615 rad`; Isaac's was
`0.000407 rad`. These values are a first control-coordinate baseline, not an
automatically applicable learned residual or a mechanical output-angle
calibration.

## Safety

The default router is simulator-only. Physical routing requires a named trial
authorization, fresh real state, one command publisher, mechanical limit
checks, a per-joint excursion bound, an explicit return, and router cleanup.
Do not use the physical runners without a current operator authorization and a
clear workspace.

## Quick start

1. Run `alignment/real_sim_gap_agent.py` to verify both state streams.
2. In Isaac Sim, run `alignment/isaacsim_gap_control_daemon.py` once.
3. Repair simulator drives through
   `/openarm/isaac_gap/repair_all_arm_drives`, then run
   `alignment/run_sim_only_fixed_point_baseline.sh`.
4. Create a fresh, explicitly authorized physical manifest before running
   `alignment/run_real_sim_fixed_point_baseline.sh`.
