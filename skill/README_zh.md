# OpenArm Isaac Sim2Real 最小闭环流程

本流程将真实机械臂的可重复关节误差做成 **Isaac compare/replay 标定**。它不改真机命令、USD、URDF 或 Isaac drive。

## 产物

- 原始证据：每轴带时间戳的真机/Isaac feedback、router receipt 和 manifest。
- 分类候选：`q_real = a*q_sim + b + h(direction)`，并单列 delay 与残差方差。
- 标定文件：`alignment/calibrations/openarm_isaac_replay_calibration_v3.json`。
- 验证报告：留出重复回放和 Isaac-only compensated replay。

## 闭环

1. **只读健康检查**：确认 real `/joint_states`、Isaac `/sim/openarm/joint_states_v2`、名字映射、频率和新鲜度；先修复任何 Isaac sim-only tracking 失败。
2. **真实采集前门控**：每次真实试验要求独立、命名的授权；确认急停、清场、安全姿态、断电位置、唯一发布者、CAN UP 与绿灯。未通过只做只读诊断。
3. **受限多点采集**：逐轴执行 measured-start → `+0.05` → start → `-0.05` → start → `+0.10` → start；50 Hz、每点 3 s、总偏移 ≤0.15 rad。每个 waypoint 必须有 accepted receipt。
4. **离线分类和拟合**：用 `fit_openarm_gap_model.py` 区分静态偏置、比例/传动、方向迟滞、随机残差和 delay。缺失、stale 或未跟踪的轴不生成补偿项。
5. **留出验证**：用未参与拟合的重复数据比较 raw MAE 和 emulated MAE。没有改善或跨轴 router 异常的轴标为 provisional，不能启用。
6. **导出与导入 Isaac**：用 `assemble_isaac_replay_calibration.py` 输出 v2 JSON；通过 `deploy_isaac_compensation_replay.sh` 同步到 Isaac 主机，重载 daemon，调用 `enable_compensation_replay`。
7. **Isaac-only replay 验收**：router 必须 `enable_real=false`；每轴要求 target 和 return receipt 都存在且跟踪通过。确认 `real_sent=false`，再把报告归档。

## 导入规则

对启用轴，bridge 仅在 Isaac 侧应用：

```text
q_emulated = a*q_nominal + b + h(previous_nominal_direction)
```

单位均为 rad；原始 receipt 保持名义目标。`enabled_for_isaac_replay:false` 的轴必须原样透传。比例项还需核对单位、轴方向、传动比与限位；delay 未从端点数据识别时不得伪造固定值。

## 可复用命令

```bash
/usr/bin/python3 alignment/validate_isaac_replay_calibration.py \
  --config alignment/calibrations/openarm_isaac_replay_calibration_v3.json

bash alignment/deploy_isaac_compensation_replay.sh
# 在 Isaac Script Editor 重载 isaacsim_gap_control_daemon.py 后：
ros2 service call /openarm/isaac_gap/enable_compensation_replay std_srvs/srv/Trigger '{}'
```

真实命令永远不由该标定文件触发。对 provisional 轴进行新的真实复验，需要新的逐次授权。
