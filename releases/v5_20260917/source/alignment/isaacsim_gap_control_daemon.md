# Isaac Sim Gap Control Daemon

Run `isaacsim_gap_control_daemon.py` once in Isaac Sim Script Editor after opening the OpenArm measurement scene. The daemon immediately loads the state publisher and timestamped command bridge, then exposes read-only/management ROS services. It does not publish a robot command.

From any ROS shell that can see Isaac Sim:

```bash
ros2 service call /openarm/isaac_gap/status std_srvs/srv/Trigger '{}'
ros2 service call /openarm/isaac_gap/ensure_all std_srvs/srv/Trigger '{}'
```

Use `ensure_state` or `ensure_bridge` to reload only the affected module. After each service call, the agent must run `real_sim_gap_agent.py` and treat its actual topic observations as the validation result; a successful service response only means that loading was queued.

The daemon uses `/home/tangyuan/openarm_ws/alignment` on the Isaac host. Change `ALIGNMENT_DIR` only if that workspace has a different path there.
