# Autonomous discovery and validation

Use this reference whenever the request is to build, repair, validate, extend, or operate the Sim2Real integration.

## 1. Discover before deciding

Read the project integration ledger first:

`/home/tangyuan/openarm_ws/alignment/openarm_isaacsim_sim2real_integration.md`

Then inspect the current workspace with targeted searches. Locate the actual, current versions of:

- real hardware bringup, controller YAML, hardware plugin, and controller topics under `src/openarm_ros2/`;
- policy/VLA configuration and existing ROS client code under `src/openarm_infer/`;
- Isaac Script Editor bridge, state publisher, analysis, capture, and launch helpers under `alignment/`;
- active output/session artifacts under `alignment/results/`.

Use `rg --files` and `rg` first. Do not assume a path, ROS container name, topic, DOF order, controller, or scene is still valid because it appeared in an old note. Compare each discovered fact against the ledger and report any mismatch.

## 2. Form a concrete plan

For each request, independently make a short execution plan containing:

1. desired observable result;
2. modules and files that implement it;
3. dependency order;
4. validation command or inspection for each module;
5. what is read-only versus what can cause physical motion;
6. output files and the document to update.

Proceed through read-only discovery, static validation, and simulation-only validation without asking for routine confirmation. Before a command can reach real hardware, provide the exact proposed action, limit, return behavior, and validation criterion; wait for the operator's explicit authorization for that specific trial.

## 3. Test modules from low risk to high risk

Use the narrowest meaningful validation:

| Module | First validation | Completion evidence |
|---|---|---|
| Python helper | `python3 -m py_compile` and relevant deterministic invocation | exit status and output artifact |
| ROS adapter | import/topic type inspection and read-only echo | named topic, type, endpoint and one message |
| Isaac Script Editor publisher/bridge | inspect console marker and container-side read-only echo | expected marker plus one message/receipt |
| Cross-host DDS | probe plus real and simulation state observations | both state topics visible at required endpoint |
| Canonical mapping | compare discovered named joints against mapping profile | no duplicate/missing required names |
| Measurement analysis | run it on an existing recorded session first | reproducible metrics file |
| Physical command | operator-approved low-amplitude single-joint trial | command, feedback, return, and recorded evidence |

Never use a discovery scan that reconfigures CAN or changes motor state as a routine health test. Do not treat endpoint discovery as proof that callbacks publish data; require one actual message.

For a paired physical trial, validate receipt, target-window feedback, and return-window feedback independently for real and simulator. A router receipt is transport evidence only. If only the simulator tracks, stop the real router, preserve the raw samples, and inspect the real hardware plugin's active configuration, motor IDs/types, control mode, feedback freshness, and command-hold behavior without issuing a new command. Do not fold a non-tracking real sample into residual calibration.

If a direct, guarded, fixed-rate controller-topic test moves a real joint but an otherwise equivalent one-shot router command does not, classify the fault as an action-delivery contract mismatch before suspecting the motor or CAN. Record the direct test's rate, hold duration, target and feedback. Update the router design to stream only a previously accepted, bounded target during an explicitly authorized trial window; use a bounded return trajectory and stop the real router afterwards. Do not change real router behavior or run that streaming trial without a fresh named authorization.

## 4. Maintain a live issue loop

When a validation fails:

1. isolate the failing module from adjacent modules;
2. capture exact command, stdout/stderr, topic information, or Script Editor marker;
3. identify the smallest correction supported by that evidence;
4. re-run only the affected validation and dependencies;
5. append issue, cause, correction, and result to the integration ledger.

Use `alignment/README.md` for detailed invalid trials and troubleshooting. Use `alignment/isaacsim_measurement_log.md` only after an output artifact supports an interpretable numerical result.

## 5. Definition of done

A requested capability is complete only when its source/configuration is located, its relevant modules have been validated, its evidence artifact exists, and the ledger reflects its current state. If a live dependency is unavailable, finish all offline and read-only work, identify the exact remaining check, and leave the integration in a reproducible state.
