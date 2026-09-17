# J7 动态 Gap：Isaac-only 排除与调参流程

此流程针对已测到的 J7 `real−Isaac t90≈−0.81 s`：真机比 Isaac 更快。它只改 **当前 Isaac live USD session**，不发送真机命令，也不持久改基础 USD。

## 判定逻辑

1. 先记录 bridge 的 `command_received → target_applied → first_physics_response → state_published` 四个单调时钟时间点。
2. 若前两段耗时大，先修 bridge 或 state publisher；若 target 已及时施加但 physics response 很慢，才调 drive/solver。
3. 首轮只扫 J7 drive 的 stiffness、damping、max force。physics `dt/substeps` 独立扫描，避免把两个因素混在一起。
4. 每个候选用 `±0.025/±0.050 rad`、三次重复进行 Isaac-only 采集；目标平均 `t90=0.10–0.15 s`，超调比例不超过 10%。
5. 只有第一轮通过后，才以 `±0.015/±0.040 rad` 和 return 曲线复验。仍通过时才能写入单独的 USD override/calibration layer；基础 USD 保持不变。
6. 动态层通过后，才和静态 v3 replay 联合验收。原始动态曲线采集必须继续关闭静态 replay。

此逻辑适用于所有 14 个关节，但参数不能跨轴复制。先运行全轴 Isaac-only baseline，只有已通过真机配对动态采集的轴，才拥有“Isaac 比真机慢/快”的动态 gap 结论和对应调参目标。

```bash
bash alignment/run_isaac_only_dynamic_baseline_all_arms.sh
```

它只提供各轴的 Isaac 响应基线；它不会对真机作任何推断，也不改变 drive。

当前 v1 全轴基线表明多数轴 t90 在约 `0.9–1.1 s`，因此优先检查共享的 PhysX/control 配置。左 J4 的负向小幅响应接近有效阈值，不能参与参数拟合；应先在远离限位的位置重采。

### 已完成的 PhysX 频率排除

在保持原始 J7 drive（stiffness `100`、damping `10`、max force `7`）的条件下，分别以 live session 的 `120 Hz` 与 `240 Hz` 运行同一条曲线。120 Hz 得到 `t90=1.049 s`、onset `0.192 s`、最大超调 `5.05%`（11 个有效阶段）；240 Hz 得到 `t90=1.150 s`、onset `0.232 s`、最大超调 `11.01%`（12 个有效阶段）。两者均未通过 `0.10–0.15 s` 及超调门槛，240 Hz 还使响应和超调变差。

因此已恢复 PhysicsScene 的扫描前快照；不得将 120 或 240 Hz 写入 USD override layer。该结果排除了“只提高 PhysX timestep rate”作为主修复方向，但不能排除 drive、Kit-update 频率、控制器语义或场景动力学的组合问题。

在继续扫描控制更新率前，必须同时记录墙钟和 Isaac timeline 时间。墙钟 `t90` 反映端到端实时闭环，timeline `t90` 反映物理模型自身推进；若两者显著不同，先报告 simulation real-time factor，不能把渲染或主机算力不足误拟合成关节 drive 参数。

部署 timestamp 更新后，先在 timeline 为 Play 时运行只读实时倍率探针：

```bash
ros2 service call /openarm/isaac_gap/measure_realtime_factor std_srvs/srv/Trigger '{}'
ros2 topic echo /openarm/isaac_gap/realtime_factor_json std_msgs/msg/String \
  --once --qos-durability transient_local --qos-reliability reliable
```

探针连续测量 10 秒，输出 UI timeline、Kit update Hz 与 p95 帧间隔，同时以 PhysX step callback 累计 `physics_advanced_s`。用 `physics_realtime_factor = physics_advanced_s / wall_window_s` 判断真实物理推进速度，不能只依赖 UI timeline。`physics_realtime_factor < 0.95` 时先调查 GPU/CPU 饱和、渲染负载、stage 复杂度、物理步进与 update 抖动；在问题消除或明确作为部署约束前，不能按墙钟 t90 拟合 drive。`physics_realtime_factor≈1` 而 physics-time t90 仍慢，才进入 drive/control-rate 候选扫描。

本机 2026-09-16 的探针已测得 `physics_realtime_factor=0.2725`：10.03 s 墙钟内 PhysX 仅推进 2.733 s，physics step 为固定 16.67 ms、频率却仅 16.35 Hz；Kit update 仅 24.42 Hz，p95 间隔 53.76 ms。这是当前动态墙钟 gap 的首要运行层原因，先读取 `/persistent/simulation/minFrameRate` 与 `/app/runLoops/main/rateLimitFrequency`，并对 GUI、无渲染与传感器关闭条件分别复测。不得在该问题未排除前继续调 drive 或写 USD layer。

已读到运行时设置：`minFrameRate=30`、`rateLimitFrequency=72 Hz`。当前 app 实际约 24 Hz，因此 72 Hz rate limit 未触发；30 Hz PhysX catch-up clamp 是首个可检验原因。先只在 live session 扫 `minFrameRate=15`、`10`，每项运行实时倍率探针后恢复快照。降低 clamp 允许慢 app frame 补跑更多物理步，可能降低 GUI 响应，不是长期性能修复；若有效，再以 GUI/传感器关闭/headless 对照定位渲染负载。

扫描结果：15 的 `physics_realtime_factor=0.2697`，10 为 `0.3151`，均远低于 1；降低 clamp 只带来有限改善且 Kit update 更慢。恢复 30 后，下一项是单独关闭 active viewport 更新的 A/B 试验；它不影响 USD、PhysX 参数或机器人 target。若 viewport 关闭仍无明显改善，优先停用 Replicator/RTX 传感器，再运行 headless 基准与 Tracy/Isaac benchmark，而不是继续降低 clamp。

viewport A/B 已完成：关闭 active viewport 更新后，`physics_realtime_factor` 从 `0.2725` 提升到 `0.6628`（约 `2.43x`）；PhysX step 从 `16.35 Hz` 提升到 `39.77 Hz`，Kit update 从 `24.42 Hz` 提升到 `59.35 Hz`。因此当前慢响应的首要原因是 GUI viewport/RTX 渲染负载，**不是 USD 中 J7 drive 或 PhysX dt 的证据**。该测试仅修改 live session 的 `viewport.updates_enabled`，已通过 restore service 恢复。剩余 `0.3372` 的实时倍率缺口需以 Replicator RenderProduct/RTX 传感器和 headless A/B 继续隔离；在此之前，J7 的墙钟 `t90` 不可作为 drive 参数拟合依据。

## 部署到 Isaac 主机

```bash
cd ~/openarm_ws
bash alignment/deploy_isaac_j7_dynamic_tools.sh tangyuan@192.168.18.72
```

在 Isaac Sim Script Editor 再次执行 `alignment/isaacsim_gap_control_daemon.py` 的完整内容。随后确认：

```bash
ros2 service call /openarm/isaac_gap/status std_srvs/srv/Trigger '{}'
```

必须显示 `state=True bridge=True compensation_replay=False`。Isaac timeline 必须处于 Play。

## 扫描一个候选

以下命令只改变远端 live session；`apply` 前会把 J7 target 置为当前姿态，避免候选切换本身造成跳变。

```bash
cd ~/openarm_ws
python3 alignment/select_right_j7_dynamic_drive_candidate.py j7_drive_p1
bash alignment/deploy_isaac_j7_dynamic_tools.sh tangyuan@192.168.18.72
ros2 service call /openarm/isaac_gap/apply_right_j7_dynamic_drive std_srvs/srv/Trigger '{}'
bash alignment/run_isaac_only_j7_dynamic_candidate.sh j7_drive_p1 fit
```

依次将候选改为 `j7_drive_p2`、`j7_drive_p3`、`j7_drive_p4`，重复以上四步。完成后评分：

```bash
python3 alignment/score_isaac_j7_dynamic_candidates.py \
  --output alignment/results/isaac_j7_dynamic_drive_sweep_score_v1.json
```

若输出 `no_candidate_passed`，不得写 USD；保留结果，下一轮单独审计 velocity limit、control rate 和 solver 指纹。若有候选通过，用该候选做不同幅值复验：

```bash
bash alignment/run_isaac_only_j7_dynamic_candidate.sh j7_drive_pN validation
```

四个 drive-only 候选均未通过时，先恢复 live baseline，再执行只读诊断：

```bash
ros2 service call /openarm/isaac_gap/restore_right_j7_dynamic_drive std_srvs/srv/Trigger '{}'
ros2 service call /openarm/isaac_gap/diagnose std_srvs/srv/Trigger '{}'
```

诊断 JSON 在 Isaac 主机的 results 目录。拉取并打印摘要：

```bash
bash alignment/fetch_isaac_physics_fingerprint.sh tangyuan@192.168.18.72
```

诊断 JSON 的 `physics_fingerprint` 必须记录 solver、substeps、timestep、velocity/iteration 与 gravity 等已 author 的属性。之后才能单独设计 dt/substeps 或 velocity-limit 扫描；不要把它们与 drive gain 同时改变。

回滚 live session：

```bash
ros2 service call /openarm/isaac_gap/restore_right_j7_dynamic_drive std_srvs/srv/Trigger '{}'
```

## 后续持久化门

通过不同幅值验证只产生候选。持久 USD override 层还必须记录：候选 ID、四段 timing、drive 参数、solver dt/substeps、场景 hash、曲线和验证 JSON 的 SHA-256。随后加载静态 v3 replay 与该动态 layer，完成一次 14 轴 Isaac-only 联合验证；真实独立 session 验证仍是长期默认配置的门槛。
