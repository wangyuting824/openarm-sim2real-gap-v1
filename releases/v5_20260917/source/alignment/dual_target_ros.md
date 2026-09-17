# Isaac Sim 与真机共用 ROS 控制入口

统一输入 topic：`/openarm/command`，类型为 `sensor_msgs/msg/JointState`。命令按关节名匹配，不能依赖数组顺序。

```text
/openarm/command
  └─ dual_target_command_router.py
       ├─ /sim/openarm/timestamped_joint_command → Isaac Sim
       ├─ /left_forward_position_controller/commands → 真机左臂
       ├─ /right_forward_position_controller/commands → 真机右臂
       ├─ /left_gripper_forward_position_controller/commands → 真机左夹爪
       └─ /right_gripper_forward_position_controller/commands → 真机右夹爪
```

状态保持隔离：Isaac Sim 为 `/sim/openarm/joint_states_v2`，真机为 `/joint_states`。router 的可审计分发结果发布到 `/openarm/dual_command_receipt`。

## 启动

先在 Isaac Sim Script Editor 启动 `isaacsim_timestamped_command_bridge.py`。主机上启动 router，初始仅驱动仿真：

```bash
source /opt/ros/jazzy/setup.bash
source "$HOME/openarm_ws/install/setup.bash"
python3 "$HOME/openarm_ws/alignment/dual_target_command_router.py" \
  --ros-args -p enable_real:=false
```

确认 router 的 `/openarm/dual_command_receipt` 持续报告 `sim_only_real_disabled`，以及 Isaac receipt/state 正常后，才启动唯一一套真机 bringup。确认真实 `/joint_states` 具有左右 14 个关节和两个 finger joint 的完整反馈后，才可由操作员以一个本次试验专用的 authorization ID 启用真机路由：

```bash
/usr/bin/python3 "$HOME/openarm_ws/alignment/dual_target_command_router.py" \
  --ros-args \
  -p enable_real:=true \
  -p real_authorization_id:=operator-approved-trial-001 \
  -p max_delta_rad:=0.02 \
  -p real_state_max_age_s:=0.25
```

启用后，router 会拒绝：空 authorization ID、反馈不完整或超时、未知关节、越过 `mechanical_limits.csv` 的目标、单次变化大于 `max_delta_rad` 的目标，以及 controller command topic 存在多个 publisher。Agent 不应自行生成 authorization ID 或重试被拒绝的真实动作；急停/Deadman 仍是独立的物理安全层。

## 无运动验收

使用当前关节位置作为目标，先只验证链路。命令示例仅发送左/右 J1，且 router 在 `enable_real:=false` 时只会进入 Isaac：

```bash
ros2 topic pub --once /openarm/command sensor_msgs/msg/JointState \
  "{name: [openarm_left_joint1, openarm_right_joint1], position: [-0.0261804564, 0.0271758609]}"
```

真机启用前检查：一个 `controller_manager`、左右控制器均为 `active`、每个 commands topic 恰有一个 router publisher 和一个 controller subscriber、无 KER 或旧 bringup 残留进程。
