# Startup profiles and control authority

Read this reference before starting or recovering a process.  First identify the
host and check for an existing process; do not create a duplicate publisher,
bridge, or controller manager.

## Host profiles

| Profile | Host | Entry point | Agent autonomy | Effect |
|---|---|---|---|---|
| `isaac_clean` | Isaac host `tangyuan` (`192.168.18.72`) | `alignment/start_isaacsim_clean.sh` | May start/restart after confirming no active Isaac instance conflicts | Starts Isaac with contaminated ROS/Python environment removed; it does not control hardware. |
| `isaac_streaming_ros` | Isaac host | `alignment/start_isaacsim_ros_udp.sh` | May start/restart after checking the launcher, DDS profile and existing Isaac process | Starts Isaac streaming with ROS 2 bridge and domain 42; it does not control hardware. |
| `isaac_gap_daemon` | Isaac Script Editor | `alignment/isaacsim_gap_control_daemon.py` | Agent can call its services after the operator has run this bootstrap once per Isaac process | Loads/reloads only state publisher and simulator command bridge; never publishes a robot command. |
| `sim_router` | ROS-capable host | `alignment/start_sim_only_router.sh` | May start or recover after ensuring no existing router has the same node/topic route; the wrapper refuses duplicates | Sends only to Isaac. |
| `real_bringup` | real host `tangyuan-System-Product-Name` (`192.168.18.154`) | `alignment/start_real_openarm.sh` | **Requires explicit operator authorization for this session** | Enables motors and the hardware plugin may return the arms to zero. |
| `real_router` | real host | router with `enable_real:=true` and a nonempty `real_authorization_id` | **Requires explicit authorization for this named trial** | Can send an accepted action to the real forward controllers. |

Use ROS domain `42`, `ROS_LOCALHOST_ONLY=0`, and `rmw_fastrtps_cpp` on every
host participating in a cross-host trial.  A local shell can start only
processes on its own host; do not claim to have started a remote host without
an available remote execution channel.

## Recovery sequence

1. Run read-only `real_sim_gap_agent.py` and inspect the active ROS graph.
2. If Isaac state or bridge is missing and the daemon service exists, call
   `/openarm/isaac_gap/ensure_state`, `/ensure_bridge`, or `/ensure_all`.
3. Re-run health. A service receipt alone is not evidence of state publication.
4. If tracking is wrong despite a receipt, call `/openarm/isaac_gap/diagnose`,
   read `alignment/results/isaacsim_joint_drive_probe.json`, and diagnose the
   live USD drive before proposing a gain/limit repair.
5. A temporary correction may be trialled only in Isaac and must be followed
   by `measure_sim_only_router_tracking.py`. Persist no USD or controller
   change until the probe and test show why it is needed.

## Real-hardware gate

Never automatically launch `real_bringup`, enable motors, clear a fault, or
switch the router to `enable_real:=true`. These actions can cause motion.
Require a direct authorization that names the upcoming trial after the
operator confirms emergency stop, clear workspace, known posture, no other
command publishers, and a person at the power cutoff.  The router's
`real_authorization_id`, limits, stale-feedback check, and max delta are
technical gates; they do not replace operator authorization.
