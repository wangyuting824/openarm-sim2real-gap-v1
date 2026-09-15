---
name: openarm-sim2real-gap
description: Measure, diagnose, and reduce the OpenArm/SO101 Isaac Sim-to-real gap for reusable manipulation skills or a Pi0.5 VLA agent. Use for real-plus-simulation ROS alignment, domain randomization, residual calibration, and evidence-backed sim-to-real evaluation; do not use for a simulator-only experiment.
---

# OpenArm Sim2Real Gap

Use this skill to turn an Isaac Sim policy into a real-robot experiment with explicit evidence. Separate three concerns:

- **Skill:** a reusable, bounded action primitive such as grasp, place, or push.
- **Agent:** perception/planning that selects a skill and may request a bounded residual correction.
- **Safety supervisor:** validates state, limits commands, and can stop execution. It remains independent of the policy.

## Start with the operating mode

Choose the smallest mode that answers the request:

1. **Health:** confirm the real and Isaac state streams are visible. This is read-only.
2. **Measurement:** execute an explicitly approved, bounded trajectory on both targets and record state, timing, and observations.
3. **Calibration:** estimate static offsets, latency, scale, or direction-dependent error from a completed measurement.
4. **Training:** configure domain randomization, fit a residual model, or prepare real-data replay.
5. **Deployment:** connect a selected skill or VLA policy to the guarded executor.

For the OpenArm + Isaac Sim v0 implementation, first read the project source of truth: `/home/tangyuan/openarm_ws/alignment/openarm_isaacsim_sim2real_integration.md`. It records the active topic contract, host split, issue IDs, repairs, and next iteration. For every engineering task, read [autonomous discovery and validation](references/discovery-and-validation.md) before choosing files, tests, or a repair. Read [the execution reference](references/execution.md) for generic topic contracts, evidence files, and physical-control gates. Read [the startup profiles](references/startup-profiles.md) before starting or recovering a process. Read [the Isaac tracking diagnostic](references/isaac-tracking-diagnostic.md) when receipt and feedback disagree. Read [the open-source resources](references/open-source-resources.md) when researching an observed Sim2Real issue. Read [the model reference](references/modeling.md) for randomization, residual learning, and evaluation design.

## Agent operating contract

Act as the integration engineer. Independently locate the current implementation, form an evidence-backed plan, execute read-only and simulation-only validations, and maintain the issue ledger. Do not stop after suggesting commands when an executable local validation is available. Before any real-hardware command, keep the action operator-gated; that is the only step that requires explicit trial authorization. The agent may autonomously start/recover Isaac and run simulator-only checks when it has execution access on that host. It must inspect existing processes and topic publishers first. It may not auto-launch real bringup, enable motors, clear faults, or switch a router to real mode: `start_real_openarm.sh` can enable motors and return the arms to zero.

## OpenArm + Isaac Sim v0 route

When the request concerns the current OpenArm deployment, use the integration document as the authoritative operational record. In particular:

- Treat I-009 as blocking until Isaac publishes `/sim/openarm/joint_states_v2` and it is visible in the Isaac ROS container. The real state stream and cross-host probe alone do not make a dual-target trial ready.
- Use `alignment/real_sim_gap_agent.py` for one-command read-only health evidence once both streams are available.
- When `isaacsim_gap_control_daemon.py` is running in Isaac, use its standard Trigger services to restore only missing Isaac modules, then rerun health; do not ask an operator to repaste a bridge script for a recoverable module. When command receipt and tracking disagree, call `/openarm/isaac_gap/diagnose`, inspect `results/isaacsim_joint_drive_probe.json`, and repair only the live simulator after evidence identifies a bad bridge target, callback conflict, drive, force, or limit.
- Treat a paired trial as two independent tracking validations. `sim_sent=true`, `real_sent=true`, and controller receipt prove transport only. Calculate target-window and return-window feedback separately for both endpoints. If Isaac reaches the target and real hardware does not, stop the real router after the declared return, record the result, and perform only read-only hardware-plugin/CAN/control-mode audits. Do not compensate by increasing a target, changing gains, fitting a residual, or launching another real trial without a new named authorization.
- Once an operator explicitly authorizes a named physical manifest with its maximum excursion and return behavior, the agent—not the operator—must launch the guarded router, publish the canonical trajectory, record receipts and feedback, stop the real router, and write the evidence. For OpenArm streaming trials, use `real_publish_hz` only with a nonempty authorization ID; keep the default at zero. Do not replace the manifest's mechanical bound with unbounded manual `ros2 topic pub` commands.
- Record a new issue, decision, fix, and validation result in `alignment/openarm_isaacsim_sim2real_integration.md`; retain detailed invalid trials in `alignment/README.md` and valid metrics in `alignment/isaacsim_measurement_log.md`.
- For a new robot or simulator, create a new adapter profile instead of changing the OpenArm-specific mapping or topic names.

## Preserve these OpenArm invariants

- Real feedback is `/joint_states`; Isaac feedback is `/sim/openarm/joint_states_v2`. Do not merge them by topic name.
- The real bimanual controller publishes 16 joints: each arm has 7 arm joints and one finger joint. The Isaac articulation has 18 DOF. Establish and record an explicit name-based mapping before comparing vectors; never compare by index alone.
- A command target is not a measured state. Use post-command feedback and receipt timestamps for delay and tracking metrics.
- Use exactly one active publisher per command route during a measurement. Duplicate Isaac Script Editor callbacks invalidate a run.
- The existing `alignment/real_sim_gap_agent.py` is read-only and is the first preflight check. A health failure blocks calibration and policy evaluation, but does not diagnose wiring by itself.

## Physical-control gate

Before any command that may reach hardware, require the operator to explicitly authorize that particular trial and verify the work area, emergency stop, motor state, and a known return posture. Keep a single-joint low-amplitude motion as the first active test. Do not enable motors, clear faults, launch hardware, or apply fitted corrections merely because the agent is running.

For a command trial, define before execution:

- the selected joint/skill, initial and final targets, limits, rate, hold time, and return target;
- the real and simulation topics, joint mapping, sampling window, and output directory;
- abort criteria for absent state, stale state, out-of-limit position, tracking error, or operator stop.

Stop the run on the first failed gate. Write the reason to `alignment/README.md`; only valid numerical evidence belongs in `alignment/isaacsim_measurement_log.md`.

After the declared return command, stop any `enable_real:=true` router before analysing data. A real/sim offset is eligible for calibration only after repeated, accepted trials establish that both endpoints tracked their declared targets and returned within the manifest tolerance.

## Build the adaptation layer in this order

1. **Observation alignment:** calibrate camera intrinsics/extrinsics and object pose frame conventions. Treat camera observations and joint feedback as timestamped streams.
2. **Action alignment:** use a common canonical action representation, then map it separately to Isaac and real controllers. Apply rate, position, and effort/torque restrictions at the real adapter.
3. **Residual estimation:** begin with interpretable static offset, scale, delay, and direction-dependent terms. Introduce a learned residual only when held-out data shows it improves task-relevant error.
4. **Policy adaptation:** train or fine-tune the skill/VLA with simulation plus approved real trajectories. The online residual must be bounded and supervised.
5. **Evaluation:** hold out task instances, seeds, objects, lighting, and real trials. Report success rate, terminal pose error, timing, safety stops, and correction magnitude.

Use the model relation `u_real = clip(u_sim + Δu, limits)` only after the mapping and limits are specified. `Δu` is a correction proposal, not permission to exceed a controller or mechanical limit.

## Deliverables

For each completed mode, leave reproducible artifacts: configuration, topic mapping, timestamped raw data or bag, metrics, and a concise result entry. Include domain-randomization seed/ranges and real-data provenance for any learned model. State what remains unmeasured rather than inferring real-world performance from Isaac-only results.
