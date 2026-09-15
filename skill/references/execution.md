# Execution reference

## ROS topology

- Real host: native ROS Jazzy, real hardware bringup, CAN adapters, and `/joint_states`.
- Isaac host: Isaac Sim plus the ROS container. The container should discover the real host and expose Isaac topics to the same ROS domain.
- Use the same `ROS_DOMAIN_ID` and RMW implementation on every participating shell. A cross-host probe only proves discovery; both actual state topics must be observed before an experiment.

## Fast health check

Run the health agent in the Isaac ROS container after its workspace is mounted or copied into that container:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
/usr/bin/python3 /path/to/alignment/real_sim_gap_agent.py \
  --duration-s 5 --output /path/to/results/real_sim_gap_health.json
```

It checks real `/joint_states` and simulation `/sim/openarm/joint_states_v2`; it does not send a command. A health report is ready only after the real stream contains at least 16 names and the simulation stream at least 18 names.

If Isaac state is absent in the container, restore the single Script Editor state publisher and confirm `OPENARM_STATE_PUBLISHED`. If it is present in the container but absent on the real host, inspect DDS discovery/profile configuration. Do not begin trajectory trials until the state path is bidirectional.

## Canonical action and mappings

Represent an action with named targets and a timestamp, never an unlabeled vector. A trial manifest must include:

```yaml
trial_id: right_j7_step_001
canonical_action:
  openarm_right_joint7: 0.02
real_target_topic: /right_forward_position_controller/commands
sim_target_topic: /sim/openarm/timestamped_joint_command
real_state_topic: /joint_states
sim_state_topic: /sim/openarm/joint_states_v2
mapping_version: named-map-v1
```

The real controller arrays are arm-local and have 7 entries. Isaac messages contain the articulation's DOF names. Derive each target vector from the recorded name map rather than a hard-coded alternating order.

## Measurement evidence

A valid active trial needs all of the following:

- one logged canonical command and both target-route receipts when available;
- real and simulation feedback covering pre-command, motion, and settle windows;
- an explicit zero/return command or documented end condition;
- numeric position error, settling criterion, delay definition, and sampling metadata.

Keep failure, missing topic, duplicate publisher, and operator-stop notes in `alignment/README.md`. Write only completed, interpretable values to `alignment/isaacsim_measurement_log.md`.

## Agent command authority

Use three authority levels:

| Level | Agent capability | Hardware effect |
|---|---|---|
| Observe | Diagnose topics and generate reports | None |
| Propose | Generate a trial manifest and correction candidate | None until operator approval |
| Execute | Send the approved bounded trial through one guarded route | Limited to the declared trial |

The agent must return to Observe after an abort, topic loss, stale feedback, or completion. It must not retry physical actions autonomously.
