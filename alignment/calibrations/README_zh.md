# OpenArm Isaac Replay 标定文件

当前导入文件：`openarm_isaac_replay_calibration_v3.json`。

它将命名的名义关节目标转换为 Isaac replay 中的真机等效目标：

```text
q_emulated = a × q_nominal + b + h(approach_direction)
```

`approach_direction` 由同一关节的上一个名义目标决定，取 `positive`、`negative` 或 `hold`。输入和输出单位均为 rad。

## 导入范围

- 这是 Isaac compare/replay 标定，不能用于真机命令补偿。
- `enabled_for_isaac_replay: true` 的 14 个关节可由 replay bridge 使用。
- 右 J7 已完成独立真机复验；其状态化正反向补偿已纳入 v3。
- 比例项 `a` 仍要求核对轴方向、单位、传动比和限位；它不是自动修改 USD、URDF 或 drive 的许可。
- `delay` 未测得，保持未设置；随机噪声也不写成固定 offset。

## 在 Isaac 主机导入

从旧主机运行：

```bash
cd ~/openarm_ws
bash alignment/deploy_isaac_compensation_replay.sh
```

在 Isaac Script Editor 重新执行 `isaacsim_gap_control_daemon.py`，然后通过 ROS 调用：

```bash
ros2 service call /openarm/isaac_gap/enable_compensation_replay std_srvs/srv/Trigger '{}'
```

`/openarm/isaac_gap/status` 返回 `compensation_replay=True` 后，bridge 才会加载 v3 文件。停用时调用 `disable_compensation_replay`。部署和启用本身不向真机发布命令。

Script Editor 可直接执行以下完整重载语句：

```python
exec(compile(open("/home/tangyuan/openarm_ws/alignment/isaacsim_gap_control_daemon.py", encoding="utf-8").read(), "/home/tangyuan/openarm_ws/alignment/isaacsim_gap_control_daemon.py", "exec"))
```

## 导入后的验证

部署、重载并确认 service 状态后，旧主机可一条命令验证全部 14 轴。该脚本自己启动/停止 `enable_real=false` 的临时 router：

```bash
cd ~/openarm_ws
bash alignment/run_isaac_v3_compensation_validation.sh
```

这次验收应覆盖全部 14 个关节。若任意一轴未通过，应停在 Isaac-only 排障；不得因补偿失败自动重发真机命令。
