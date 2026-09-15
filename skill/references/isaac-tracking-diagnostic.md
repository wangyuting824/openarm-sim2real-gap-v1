# Isaac tracking diagnostic and repair loop

Use this loop when a simulator command receipt is present but the measured
joint does not reach its target. A receipt proves callback delivery; it does
not prove that the PhysX articulation drive applied the action.

1. Keep the router in `enable_real:=false`.
2. Run `measure_sim_only_router_tracking.py`. Save the target, return target,
   receipt flags, post-command feedback and errors.
3. Call `/openarm/isaac_gap/diagnose`, then read the retained
   `/openarm/isaac_gap/diagnostic_json` topic from any DDS-visible host.
   `/openarm/isaac_gap/events` exposes the retained concise load/error summary.
   The JSON remains at `alignment/results/isaacsim_joint_drive_probe.json` on
   the Isaac host; do not assume the real host shares that filesystem.
4. Match the intended canonical DOF to the live articulation `dof_names`, then
   inspect the associated USD angular-drive prim(s): type, target position,
   stiffness, damping, and max force. Also inspect bridge `active_target`,
   `apply_count`, static-hold state and articulation position.
5. Classify the evidence:
   - bridge target absent or wrong index: repair bridge mapping/action format;
   - multiple live target writers/static hold: remove only the conflicting
     simulator callback and rerun the sim-only test;
   - target is correct but no drive, zero/invalid stiffness, no force, or an
     implausible drive type: create a temporary Isaac-only drive repair
     proposal; do not copy a MuJoCo gain numerically without checking Isaac
     drive units;
   - target is correct and drive looks valid but feedback differs: inspect
     joint limits, articulation root, physics stepping and another controller
     callback before changing gain;
   - state itself is stale/misaligned: repair publisher lifecycle or named
     mapping before diagnosing dynamics.
6. For the identified OpenArm right J7 zero-gain fault, call
   `/openarm/isaac_gap/repair_right_j7_drive`. It snapshots the original drive,
   uses current pose as target, applies only Isaac stiffness=100/damping=10,
   preserves max force, and reloads the bridge. Run the sim-only test again.
   `/openarm/isaac_gap/restore_right_j7_drive` rolls the candidate back.
   Mark real measurement blocked until target and return tracking both pass.

This loop may be run autonomously because it is simulator-only. Any later
real paired motion remains operator-gated.
