---
name: openarm-sim2real-gap
description: Measure, diagnose, and reduce the OpenArm/SO101 Isaac Sim-to-real gap for reusable manipulation skills or a Pi0.5 VLA agent. Use for real-plus-simulation ROS alignment, domain randomization, residual calibration, and evidence-backed sim-to-real evaluation; do not use for a simulator-only experiment.
metadata:
  skill_version: "0.6.4"
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
Read [error classification and Isaac remediation](references/error-classification-and-remediation.md) after repeated paired joint measurements, before proposing any calibration or simulator change.
Read [full-stack Sim2Real gap coverage](references/full-stack-gap-coverage_zh.md) before expanding from joint replay to perception, contact, task, reliability, or safety optimization.
Read [动态 gap 识别与 Isaac replay](references/dynamic-gap-identification-and-replay_zh.md) before designing or applying any delay, bandwidth, velocity, jitter, or stateful dynamic correction.
Read [静态—动态 gap 统一工作流](references/static-dynamic-gap-playbook_zh.md) first for the single decision path covering static validation, mapping, residuals, RTF, and dynamic promotion. Read [标定生命周期：同一上电、独立上电与动态推广](references/calibration-lifecycle_zh.md) for detailed protocol requirements before deciding whether a static, dynamic, randomization, or mapping result may be promoted, repaired, or used as a default.
Read [TF、TCP 与夹爪执行器标定](references/tf-tcp-gripper-calibration_zh.md) before measuring or publishing robot-base transforms, TCP profiles, gripper opening mappings, limits, or contact-characterization ranges.
Read [手部相机手眼标定](references/hand-eye-calibration_zh.md) before calibrating an eye-in-hand camera, solving `AX=XB`, or publishing a camera-to-tool TF. Use `scripts/hand_eye_calibrate.py` for the offline solver; it never commands a robot or writes a TF tree.
Read [相机 ROS 容器启动规则](references/camera-container_zh.md) before starting a camera driver in Docker. Use `alignment/start_openarm_camera_container.sh` with an image that actually contains the selected driver; do not assume the Isaac ROS container or `ros:jazzy` can access a USB camera.
Read [第三人称 RealSense 与真实硬件 gap](references/third-person-realsense-calibration_zh.md) before calibrating a fixed RGB-D camera, TCP, depth scale, or real-only control/dynamics parameters.

Read [中文最小闭环流程](README_zh.md) for the current reusable OpenArm workflow.

> **Portable workspace note:** references use `/home/tangyuan/openarm_ws` as the original deployment path. On another machine, resolve that path to the receiver’s OpenArm workspace before executing any referenced command.

## Agent operating contract

Act as the integration engineer. Independently locate the current implementation, form an evidence-backed plan, execute read-only and simulation-only validations, and maintain the issue ledger. Do not stop after suggesting commands when an executable local validation is available. Before any real-hardware command, require explicit named-trial authorization. The agent may autonomously start/recover Isaac and run simulator-only checks when it has execution access on that host. It must inspect existing processes and topic publishers first.

When a named authorization explicitly includes **motor enable**, the agent must not stop merely because motors are unpowered. On the recorded real/CAN host it must proactively run the bounded enable-validation sequence in the deployed hardware profile, verify fresh feedback and the safety gates below, then continue the already authorized preflight and trajectory. It may not guess IDs, motor types, CAN settings or enable frames; it may not clear faults; and it must stop for a new authorization when the recorded profile, CAN response, LED confirmation, or any safety gate is absent or fails. `start_real_openarm.sh` can enable motors and return arms to zero, so invoke it only when its exact behavior is covered by the named authorization.

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

## Real-motor enable validation

Treat a ROS process being alive, an enable API returning, or an `ENABLE_SENT`
log line as **transport attempts**, not evidence that a motor is powered or
enabled.  Before a named real trajectory, follow this gate on the real/CAN
host (never on the separate Isaac host):

1. Confirm the host role and the CAN interfaces recorded in the integration
   ledger.  Do not infer the real host from the terminal prompt alone.
2. Select exactly one CAN writer: either the ROS hardware plugin or a bounded
   direct enable diagnostic.  Refuse direct access while `ros2_control_node`
   owns the bus; refuse a real router while a direct diagnostic owns it.
3. With motor-enable permission included in the named authorization, send the
   configured enable sequence and request feedback.  Verify CAN is `UP`, not
   `BUS-OFF`/error-passive, its RX counter increases, and a capture shows
   response frames on **each** selected bus.  Motor IDs/types must match the
   deployed hardware profile, not merely a source-code default.
4. If this OpenArm profile requires a continuous enable heartbeat, maintain the
   recorded heartbeat frame and rate through the enable-validation window. A
   single transmitted enable frame or a success log line is not evidence that
   motors remain enabled. Verify every expected motor ID responds stably while
   the heartbeat is active.
5. Require the operator to confirm the physical LEDs are green. A red LED,
   missing expected-ID response frames, stale/all-default feedback, heartbeat
   loss, or an unexpected CAN error is a failed safety gate. Stop the heartbeat
   and do not issue a position, zeroing, or router command; do not include the
   result in gap fitting.
5. Record the enable evidence (host, bus state/counters, profile, capture
   summary, and operator LED result) next to the trial preflight.  Only then
   start the guarded trajectory with its existing rate, bound, tracking, and
   return gates.

If the gate fails because a recorded CAN interface is `DOWN` or `STOPPED`, and
the named manifest authorizes CAN recovery, proactively stop the sole existing
CAN writer, restore that interface using the recorded bitrate/FD profile, and
verify `UP`, profile consistency, and every expected motor-ID response before
restarting the enable gate. Record the recovery result. Do not use guessed IDs,
motor types, rates, or position commands, and do not keep retrying a failed
recovery. If the failure is not an authorized recorded-profile recovery case,
perform only read-only diagnostics of DC supply, emergency stop/safety chain,
CANH/CANL and termination, CAN bitrate/FD mode, and the motor profile. A
corrected profile or a retry needs a new named approval.

When a real trial is requested but authorization is absent, the agent must prepare a named manifest and a reviewable authorization request first. It may run read-only health and simulator-only validation while waiting, but may not launch `start_real_openarm.sh`, enable motors, or create an `enable_real:=true` router. The request must name the exact trial ID, joints, trajectory, maximum excursion, rate, return behavior, abort gates, expected duration, and the operator’s required emergency-stop/workspace/power-disconnect/single-publisher confirmations. Treat approval as single-use and stop after any failed safety gate; prepare a new request for a changed trajectory or retry.

For a command trial, define before execution:

- the selected joint/skill, initial and final targets, limits, rate, hold time, and return target;
- the real and simulation topics, joint mapping, sampling window, and output directory;
- abort criteria for absent state, stale state, out-of-limit position, tracking error, or operator stop.

Stop the run on the first failed gate. Write the reason to `alignment/README.md`; only valid numerical evidence belongs in `alignment/isaacsim_measurement_log.md`.

For cross-host ROS state discovery, a recorder may retry its **pre-command,
read-only** state wait a bounded number of times.  It must publish nothing
during those retries.  If either real or Isaac state remains absent, mark that
joint invalid, stop the real router, and require a new named authorization
before any retry; never skip the missing-state joint or proceed to later axes.

Data completeness to repair incomplete joints must be bounded and per-joint.  An invalid,
missing-state, or unmeasured joint produces no calibration term.  Prepare a fresh
named manifest that names only the incomplete joints, with a finite number of
identification repetitions and a no-command state-discovery gate before each axis.  Do
not repeat physical motions "until usable": stop on the first failed safety
gate and require a new named authorization for any later retry.  Valid, complete
joints from the same protocol may be fit together; the retry does not ropen them.

After the declared return command, stop any `enable_real:=true` router before analysing data. A real/sim offset is eligible for calibration only after repeated, accepted trials establish that both endpoints tracked their declared targets and returned within the manifest tolerance.

## Build the adaptation layer in this order

1. **Observation alignment:** calibrate camera intrinsics/extrinsics and object pose frame conventions. Treat camera observations and joint feedback as timestamped streams.
2. **Action alignment:** use a common canonical action representation, then map it separately to Isaac and real controllers. Apply rate, position, and effort/torque restrictions at the real adapter.
3. **Residual estimation:** begin with interpretable static offset, scale, delay, and direction-dependent terms. Introduce a learned residual only when held-out data shows it improves task-relevant error.
4. **Policy adaptation:** train or fine-tune the skill/VLA with simulation plus approved real trajectories. The online residual must be bounded and supervised.
5. **Evaluation:** hold out task instances, seeds, objects, lighting, and real trials. Report success rate, terminal pose error, timing, safety stops, and correction magnitude.

### Offset classification contract

Do not label a single fixed-point gap as a reusable static offset.  Classify
recorded data before proposing a correction:

- A repeated, settled error at three or more target magnitudes and the same
  approach direction identifies a candidate affine term `a*q_sim + b`.
- Different settled errors after positive and negative approaches identify a
  directional/backlash candidate `h(direction)`.  Keep it separate from `b`.
- A difference in timestamped ramp response, settling time, or delay identifies
  a dynamic candidate `tau`; do not absorb it into a position offset.
- Large return residuals are evidence for a return/hold or direction-dependent
  problem, not proof of a zero-position bias.

For the current OpenArm route, run the read-only classifier
`alignment/analyze_real_sim_gap_classes.py` on completed per-joint evidence.
Its result can create an offset *candidate* only.  To identify one, propose a
new guarded physical manifest with measured-start `+0.05 -> 0 -> -0.05 -> 0
-> +0.10 -> 0` waypoints, 50 Hz hold, three repetitions, and a held-out
repetition.  The existing `bimanual_offset_identification_v1.yaml` is the
reference protocol.  Fitting and validation are offline; applying a candidate
to a real command, USD, URDF, or real controller requires a separate approval
and a bounded replay validation.

Use the model relation `u_real = clip(u_sim + Δu, limits)` only after the mapping and limits are specified. `Δu` is a correction proposal, not permission to exceed a controller or mechanical limit.


## Classify before repairing Isaac

For repeated, settled paired trajectories, run
`alignment/fit_openarm_gap_model.py` and retain its versioned candidate JSON.
The classifier reports `a`, `b`, direction terms, residual spread, and whether
delay is identifiable. It may suggest one of these layers, in order:

1. compare/replay transform for a stable static term;
2. name/unit/axis/transmission/limit audit for a scale term;
3. stateful friction/deadband/backlash proxy for a directional term;
4. measured domain randomization and robust-policy evaluation for random residuals;
5. timestamped command/observation buffers and matched control rate for delay.

A failed sim-only tracking check is an Isaac integration defect, not a measured
Sim2Real gap. Repair and validate the drive/bridge first. Keep all corrections
out of the real command path until a held-out replay validates them; permanent
USD/URDF/drive edits remain a separate, reviewable change.


After a valid multi-point fit, materialize a versioned compensation artifact
before connecting anything to Isaac.  For the current OpenArm route, use
`alignment/assemble_isaac_replay_calibration.py` to derive
`alignment/calibrations/openarm_isaac_replay_calibration_v3.json`, and use
`alignment/isaac_gap_compensation.py` for pure offline replay.  Its emulation
direction is `q_emulated=a*q_nominal+b+h(direction)`; determine direction from
the prior named target and keep `hold` separate.  Validate the exported artifact
with `alignment/validate_isaac_replay_calibration.py`.  Exclude absent or invalid
joints; mark a joint provisional (`enabled_for_isaac_replay=false`) when an
independent replay is still required, so it passes through unchanged.  Store any
inverse relation only as disabled documentation for a future approved real
command study.  A scale candidate requires a units/axis/transmission/limits
audit; a directional candidate requires alternating-direction held-out replay;
and a delay remains unset until timestamped response data identifies it.

## Cross-host Isaac replay deployment

When an Isaac-only replay bridge or calibration configuration lives on a separate
Isaac host, agents may automatically attempt a non-interactive SSH check and
deploy files when credentials are available.  If the host requires a password or the
Isaac Script Editor to rload, do not block on a repeated SSH attempt or ask for
credentials.  Leave a single deployment script and exact Script Editor reload
payload for the operator.  After the operator reloads, poll `ros2 service list`
and require the expected Inaac service before sending any sim-command.

For the current OpenArm compensated replay, deploy `alignment/deploy_isaac_compensation_replay.sh`,
reload `isacsim_gap_control_daemon.py`, and confirm `compensation_replay=True`
via `/openarm/isaac_gap/status`.  Keep the router in simulator-only mode and
validate against the compensated target, not the unadjusted nominal target.

When verifying simulator-only routing, treat a real controller topic publisher
endpoint as an allocated route, not evidence of a transmitted real command.  The current
dual-target router creates those publishers even when `enable_real=False`.  Require
the runtime parameter and each receipt to show``real_sent=false` before claiming
a sim-only run.

For a transient ROS publisher used in a sim-only check, wait for at least one
matched router subscriber before the first command.  Use a bounded discovery wait
of at least 12 seconds on this cross-host route; a 3-second miss after a prior
joint passes is DDS re-discovery failure, not a tracking or compensation failure.
Require at least one receipt in the target window and one in the return window.
If a compensation bridge stores prior targets to select direction, reload the
bridge to reset that state before a clean batch validation. A visually imperceptible
small compensated target does not disprove the bridge: use feedback/receipts as
primary evidence, and an explicitly simulator-only larger visual check only with
the Isaac timeline playing.

For stepped physical identification, begin each waypoint receipt window
before publishing the first substep, since the router can accept that substep
during the stepping loop.  Require an accepted receipt for each waypoint; abort
the joint if there is none.  Record a router stream-stale event that occurs
between joints separately from the next joint's accepted receipts.  If it stops
the previous active target before the next joint command, the router has altered
safely, but the next joint'result needs an independent replay before its
calibration term can be enabled.

## Calibration validity and deployment contract

Label validation evidence precisely. A repetition held out from the same powered
session is `within_session_holdout`; it may support Isaac compare/replay but is
not an independent-session promotion result. A lasting default needs a separate
power-cycle/session validation under recorded load, temperature, control-rate,
and scene conditions. Each calibration entry must state its valid joint-position,
velocity, payload, and direction domain; outside it, pass through unchanged or
use a separately measured randomization policy.

Never infer delay from settled endpoints. Keep delay `not_identified` until a
timestamped ramp or step measures command onset, response onset, and t90/t95.
A direction term based only on prior nominal target is an approximation: record
prior feedback, velocity, reversal, and hold time when identifying stronger
backlash/friction models. A scale candidate also requires a name/unit/sign/
transmission/limit audit before promotion.

After cross-host deployment, do not trust a successful copy or service response
alone. Record and compare the local and Isaac-host SHA-256 of the calibration,
confirm the bridge console printed that exact path, and then confirm daemon
status before simulator-only replay. A replay result verifies the bridge and
Isaac tracking; task-level claims still require independent real task evidence
such as end-effector error, contacts, and success rate.

## Dynamic-gap identification and replay contract

Do not estimate dynamic delay from a settled endpoint or mix static replay into a raw dynamic paired measurement. During raw dynamic identification, disable Isaac static compensation replay so real and Isaac receive the same canonical target; retain the static artifact only for offline separation. Record router receipt, same-recorder monotonic state-arrival times, ROS stamps, baseline/noise windows, and steady-state windows for both endpoints. Normalize each response with its own measured `q0` and `q∞`, then compare onset, t10/t50/t90/t95, settling, peak velocity and overshoot from the same receipt reference.

Use a bounded single-axis pilot before a full bimanual dynamic study. A dynamic manifest must state signed step amplitudes, repetitions, hold/return time, rate, maximum excursion, automatic return, time-series recording, and every abort gate. A held step response may use one bounded step; do not replace it with small command substeps, which alters the input and hides bandwidth. Per-joint data requires three repetitions: fit on two, reserve one as `within_session_holdout`, then validate a different amplitude or ramp and an independent powered session before promotion.

Classify a near-constant onset/t90 shift with matching normalized shape as command/observation delay, a shape/rise/peak-velocity change as bandwidth or rate/limit mismatch, directional curve differences as friction/backlash dynamics, and high repeat variance as jitter/randomization. Apply accepted terms only on Isaac: versioned command or observation FIFO, matched rate/zero-order hold, bounded velocity/acceleration/jerk or first-order response, or measured randomization. Never block the Isaac update callback to create delay, and never write a dynamic candidate to the real command path. Every dynamic configuration must state its position/velocity/payload/temperature/control-rate validity domain and evidence hashes; unset terms are `not_identified`.

For the current OpenArm route, use `alignment/measure_real_sim_dynamic_identification.py` only behind an already authorized router and analyse its raw JSON with `alignment/analyze_dynamic_gap.py`. The pilot definition is `alignment/manifests/right_j7_dynamic_pilot_v1.yaml`; it is a review artifact, not authorization. Run static/synthetic and Isaac-only checks first.

## Deliverables

For each completed mode, leave reproducible artifacts: configuration, topic mapping, timestamped raw data or bag, metrics, and a concise result entry. Include domain-randomization seed/ranges and real-data provenance for any learned model. State what remains unmeasured rather than inferring real-world performance from Isaac-only results.

## Gripper calibration workflow

The repository has an OpenArm-specific protocol and guarded runner at
`alignment/gripper_kinematic_calibration_protocol_zh.md`,
`alignment/start_homed_gripper_kinematic_scan_v1.sh`, and
`alignment/run_openarm_gripper_kinematic_scan_v1.sh`. These are the current
project tools; no vendor-supplied routine was found in the workspace that
produces a validated opening-width calibration package. Do not describe the
protocol as an official OpenArm calibration standard.

Run a gripper trial as one state machine, in this order:

1. Confirm the named side, no-load condition, clear workspace, emergency-stop
   readiness, green status, physical authorization token, and one command
   publisher. Refuse when another bringup, KER teleop, router, or duplicate
   `ros2_control_node` is active.
2. Bring up CAN-FD and exactly one real control stack. Require both CAN
   interfaces `UP`, hardware activation, automatic return-to-zero, and a
   three-second zero-settle feedback gate before moving the gripper.
3. Keep the arm at zero and scan only the selected gripper. The v2 pinch
   gripper has one commanded `finger_joint1`; the second finger is mimic. Use
   bounded position targets `0`, `-0.20`, `-0.40`, `-0.60`, `-0.7854` rad for
   closed through fully open, subject to the measured mechanical stop. Hold
   each point for at least three seconds and record command, feedback, ROS
   monotonic time, caliper opening in mm, and operator observation.
4. Repeat the points in reverse order to measure hysteresis/backlash. Stop on
   unexpected motion, contact, feedback loss, limit violation, CAN error, or
   disagreement between command and feedback; never exceed the URDF/software
   limit.
5. Fit `q_rad -> opening_width_m` separately for opening and closing paths,
   retain raw samples and a held-out intermediate point, and report MAE,
   maximum error, monotonicity, hysteresis, and the valid range. A no-load scan
   does not identify gripping force or task success.
6. Validate the same master/mimic and opening definition in Isaac-only replay.
   Publish a versioned gripper package only after held-out error and a declared
   task tolerance pass. Until then mark it `gripper_kinematic_candidate`.
   Always return to the safe zero/closed state and save the result manifest.

The runner must not silently guess motor IDs, enable frames, side mapping, or
opening direction. A shell `ros2 topic pub` command is a manual diagnostic,
not a completed calibration run; it cannot replace the timestamped scan
artifacts and zero/feedback gates above.

## Isaac-only dynamic drive attribution and tuning

When paired dynamic evidence has `real−Isaac t90 < 0` with magnitude substantially larger than onset difference, Isaac is slower than real. Do not add a delay FIFO. Before changing any drive setting, instrument and retain the four Isaac monotonic timestamps: `command_received`, `target_applied`, `first_physics_response`, and `state_published`. Attribute a slow curve to drive/physics only when target application is prompt and the `target_applied → first_physics_response` interval remains slow; otherwise repair the bridge or state publisher first.

For this case, use a simulator-only, reversible live-session sweep before any persistent asset edit. Change one group of parameters at a time: first stiffness/damping/max force, then separately physics dt/substeps with a scene fingerprint. Measure the same bounded signed steps at least three times, require the target t90 band and declared overshoot/steady-state gates, then repeat with a different amplitude and return curve. If no candidate passes, keep `no_candidate_passed` and do not write a USD layer. A passing candidate is still only a candidate until an independent powered-session validation. Persist only a separate versioned USD override/calibration layer with the parameters, scene fingerprint, timing evidence and SHA-256; never modify the base USD. Enable static compare/replay only after raw dynamic capture is complete and validate static plus dynamic layers together in Isaac-only replay.

## All-axis dynamic-gap elimination rule

Apply the dynamic attribution workflow to every arm joint, but never copy J7 or another joint's drive values across axes. First collect an unmodified Isaac-only dynamic baseline for all 14 joints with static replay disabled and a real-disabled router. This baseline ranks simulator response times but does not establish a real-minus-Isaac gap. Only an axis that also has valid paired raw real/Isaac dynamics may receive a signed dynamic target and an Isaac-side tuning study.

For each eligible axis, retain this sequence: (1) read drive and physics fingerprint, including velocity limits, solver, dt, substeps, iterations and gravity; (2) test one parameter family at a time, beginning with drive or velocity/control rate; (3) separately scan physics dt/substeps; (4) after every candidate, measure t90, onset, overshoot and steady-state error on the same bounded curve; (5) verify a passing candidate on a different amplitude and return curve; (6) persist only an independent versioned USD override/calibration layer. Never modify the base USD, URDF, or real controller. If no candidate passes, preserve the no-pass evidence and diagnose the next parameter family rather than escalating gains indefinitely.

When the all-axis Isaac-only baseline shows broadly slow t90, inspect the shared PhysicsScene before fitting per-joint gains. A high `physxJoint:maxJointVelocity` relative to the required step speed and a high solver-iteration setting rule out those specific limits as the first bottleneck; record that evidence. Scan `physxScene:timeStepsPerSecond` as a separate, reversible live-session candidate (for example 60, 120, then 240 Hz), with all joint drives held at baseline. Measure the same bounded curve after every rate, restore the snapshot on failure, and only propagate a selected shared scene setting after the all-axis validation and separate static-replay joint checks pass. Treat malformed or contradictory gravity fields as a scene-integrity audit item, not a basis for automatically changing gravity.

Before interpreting wall-clock t90 as a joint drive defect, measure actual PhysX step-time progress against monotonic wall time over a fixed window, along with Kit update rate and frame-interval jitter. The UI timeline time is supplementary only and must not substitute for a physics-step clock when it is stationary or inconsistent. Publish or retain wall-clock and physics-time t90 for every dynamic candidate. A physics real-time factor below 0.95 is a host/rendering/scene-performance finding that can itself create a deployment-rate and observation-age Sim2Real gap; resolve or explicitly constrain it before fitting drive gains. A near-one physics real-time factor with a slow physics-time t90 instead supports a drive/control/physics diagnosis. When physics time falls behind wall time, read and retain `/persistent/simulation/minFrameRate` and `/app/runLoops/main/rateLimitFrequency` together with the scene dt: the PhysX minimum-frame-rate clamp can cap catch-up substeps after slow app frames, making the simulation run in slow motion. Compare GUI, headless/no-viewport, and sensors-disabled probes before changing robot drives or USD physics parameters. If the app rate is below the configured minimum-frame-rate clamp while the separate app rate-limit setting is above the achieved rate, scan lower allowlisted min-frame-rate values in a reversible live session, measuring physics real-time factor after each candidate and restoring the snapshot on failure. A clamp scan is diagnostic only: its success permits catch-up steps but does not cure rendering or sensor overload.

## OpenArm dynamic-gap correction contract

Apply this contract whenever a paired OpenArm dynamic trial is used to tune
Isaac drive, rate limits, delay buffers, or a dynamic override layer.

1. **Separate static from dynamic.** Disable static compare/replay during raw
   paired capture so both endpoints receive the same canonical target.  Measure
   each endpoint against its own pre-step and steady-state values.  Do not turn
   a settled-position residual into a timing term.
2. **Use two time bases.** Record wall time for end-to-end deployment behavior
   and accumulated PhysX time for Isaac model response.  The UI timeline API is
   not a valid fallback when it is stationary while PhysX step callbacks run.
   Capture `command_received`, `target_applied`, `first_physics_response`, and
   `state_published`; `target_applied_physics_s` is the start time for
   physics-time response metrics.
3. **Gate correction on runtime validity.** Before classifying or tuning a
   dynamic candidate, measure `physics_realtime_factor`.  If it is below 0.95,
   report wall-time results as diagnostic only and do not tune or persist a
   drive/delay correction.  First isolate GUI viewport, Replicator/RTX sensor,
   scene, CPU, and GPU load.  Disabling the interactive viewport is allowed
   during simulator-only or RL collection and does not disable the policy's
   Replicator render product.
4. **Classify with physics-time curves.** Require at least eight valid paired
   step responses across the first two repetitions plus a third held-out
   repetition.  Compare onset, t10/t50/t90/t95, overshoot, settling, and return
   behavior.  A nearly constant timing shift with matched response shape is a
   bounded command/observation buffer candidate.  A t90/overshoot/peak-speed
   discrepancy after comparable onset is a drive, limit, interpolation, or
   control-rate candidate.  Do not add a FIFO when Isaac is slower because of
   bandwidth or runtime load.
5. **Change one Isaac factor at a time.** Scan drive stiffness/damping/max
   force, command/control update rate, velocity/acceleration/jerk limits, and
   physics dt/substeps/solver separately.  Each candidate is live-session only
   and must retain curves for t90, overshoot, steady-state error, and RTF.
6. **Promote conservatively.** A candidate must pass the held-out repetition,
   a distinct amplitude or ramp, and an independent powered/session validation.
   Only then write a versioned, independent USD override/calibration layer with
   parameter values, valid domain, scene/config hashes, response curves, and
   evidence hashes.  Never edit the base USD and never apply a fitted dynamic
   correction to the real command path without a separate named physical
   authorization.

For the current workspace, run `alignment/validate_dynamic_correction_gate.py`
after analysis.  A nonzero exit code is a hard stop for dynamic-parameter
promotion; preserve the results and repair runtime or measurement evidence
first.
