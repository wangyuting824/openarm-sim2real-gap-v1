# Real--Isaac Sim gap agent

`real_sim_gap_agent.py` is the read-only first stage of the gap workflow. Run it on the Isaac host, inside the ROS container that can discover both machines. It verifies both state streams in one command and saves reproducible evidence.

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

/usr/bin/python3 /workspace/openarm_ws/alignment/real_sim_gap_agent.py \
  --duration-s 5 \
  --output /workspace/openarm_ws/alignment/results/real_sim_gap_health.json
```

Adjust `/workspace/openarm_ws` to the workspace mount path inside the container. It reports `OPENARM_GAP_STATE=READY` when it observes the real `/joint_states` stream with at least 16 names, Isaac `/sim/openarm/joint_states_v2` with at least 18 names, and the named mapping in `openarm_isaacsim_joint_map.json` is valid. It reports `OPENARM_GAP_MEASUREMENT=READY` only when the Isaac command and receipt endpoints are also visible. Use `--mapping <path>` for another robot/simulator profile.

The next stage may send a declared low-amplitude trajectory to both targets, record their feedback, estimate offset/delay/backlash, and generate correction parameters. That stage must remain separately armed by the operator: the health stage never publishes a command.
