# OpenArm 动态 Sim2Real Gap 识别与 Isaac 补齐协议

本协议衔接已完成的 v3 关节位置 compare/replay 标定。v3 只描述稳态位置关系；动态协议测量同一受限命令下真机与 Isaac 的**响应时间和响应形状**，并只把经验证的动态项加入 Isaac。

## 目标和边界

每轴分开估计以下量：

- `t_onset`：从 router accepted receipt 到关节第一次显著响应的时间；
- `t10/t50/t90/t95`：按各自实际稳态位移归一化后的响应时间；
- `t_settle`、峰值速度、超调和回程差异；
- 三次重复的均值、标准差及抖动分位数。

采集的是 `q_real(t)` 与 `q_isaac(t)`，不把最终位置误差当成时间误差。动态补偿只作用于 Isaac compare/replay 或训练随机化层；不修改真机控制器、CAN 配置、USD、URDF 或 drive 参数。对 Isaac drive 的候选调参只能先在可回滚 live session 中进行；通过独立验证后才写入单独 override/calibration layer，绝不直接修改基础 USD。

## 为什么先关闭 v3 replay

原始动态配对采集时，Isaac 和真机必须接收同一个 canonical nominal target。v3 replay 会只改变 Isaac 的等效目标，混入静态偏差，令阶跃幅度和最终位置不同，从而污染 `t10/t90` 比较。

因此采集顺序是：

1. 保留 v3 文件和其静态模型作为离线参考。
2. 关闭 `compensation_replay`，确认真机与 Isaac 接收同一带时间戳命令。
3. 采集原始动态曲线。
4. 对每一侧使用各自测得的稳态位移归一化，分离位置偏差和时间响应。
5. 仅在动态模型通过验证后，将静态 v3 与动态配置一起加载到 Isaac replay。

## 采集前必须通过的门

1. **Isaac-only 基线**：该轴 sim-only tracking 通过；Isaac timeline 处于 Play；bridge、state publisher、router receipt 都可见。
2. **时间基准**：记录同一记录机的 `time.monotonic()` 接收时刻；保存 ROS header stamp 仅作诊断。跨主机没有通过同步审计时，不直接相减两个主机的 ROS 时钟。
3. **唯一命令源**：每轴仅一个受控 router；记录 PID、节点、topic 和 receipt。无 accepted receipt 或 feedback stale 时，此轴无效。
4. **真机门控**：只在新命名授权中包含电机使能和动态轨迹时，才检查 CAN UP、反馈帧递增、绿灯、急停、清场、断电位置和安全姿态。

## 最小动态试验

先做单轴 pilot，确认时间戳、采样率和自动回程，再申请全 14 轴试验。每轴从**测得起点**开始，在同一受限位置范围内执行：

```text
起点 → +0.025 rad → 起点 → -0.025 rad → 起点
起点 → +0.050 rad → 起点 → -0.050 rad → 起点
```

- 每个目标保持 2 s，回到起点后稳定 2 s；50 Hz 持续发布同一目标。
- 每个有符号幅值重复 3 次；前两次用于拟合，第三次为 `within_session_holdout`。
- 单个目标改变不超过 `0.05 rad`，任一点相对测得起点不超过 `0.15 rad`。不得为了测动态而提高幅值。
- 阶跃是一次受限目标改变后持续保持，不使用连续小子步；子步会改变输入并掩盖带宽/延迟。安全边界由 manifest、实时 tracking 和自动回程执行。
- 每轴结束即回程并停止该轴的真实 router。任一 gate 失败立即停止，剩余轴需要新授权。

正式全轴 manifest 必须写明试验 ID、每个关节、范围、次数、hold、50 Hz、回程、最大总偏移、预期时长与 abort 条件。第一轮建议的试验 ID 为 `openarm_real_sim_bimanual_dynamic_identification_v1`；它尚未被授权或执行。

## 原始记录格式

每个 waypoint 必须记录：

- canonical command、发布时刻、router receipt 时刻和 `accepted` 状态；
- real/Isaac feedback 的记录机单调接收时刻、ROS stamp、position、velocity；
- 目标前基线窗口、稳态窗口、控制频率、状态频率、场景和 drive 指纹；
- 关节名映射、起点、方向、幅值、重复编号、CAN/电机预检证据。

`receipt → state-arrival` 是端到端可比较时延；它不能单独归因给 DDS、bridge、电机或编码器。只有已审计的共同时间源才允许进一步拆分 transport 与物理响应。

## 离线计算：先消除静态影响，再比较动态

对每一侧、每个 waypoint 分别计算：

```text
q0       = 命令前稳定窗口的中位数
q∞       = 命令后稳定窗口的中位数
r(t)    = (q(t) - q0) / (q∞ - q0)
```

`q∞ - q0` 太小、符号与命令不一致、状态缺失或未稳定时，该 waypoint 无效。响应起点阈值取：

```text
max(3 × σ_pre, 0.05 × |q∞ - q0|)
```

其中 `σ_pre` 是命令前噪声标准差。随后在归一化曲线上计算 `t10/t50/t90/t95`，并测量峰值速度、超调、settling time。比较项使用同一 receipt 基准：

```text
Δt_onset = t_onset_real - t_onset_isaac
Δt90     = t90_real   - t90_isaac
```

这使 `a/b/h(direction)` 的稳态位置影响不会被误写成 delay。

## 分类与 Isaac 补齐逻辑

| 曲线证据 | 类别 | Isaac 中的候选处理 | 不应做的事 |
|---|---|---|---|
| `Δt_onset`、`Δt90` 近似常量，归一化形状一致 | 命令/观测延迟 | 版本化 command FIFO 或 observation FIFO，匹配 50 Hz 零阶保持 | 阻塞 bridge callback 或改真机延迟 |
| onset 接近但 `t90`、峰值速度或 `t_settle` 持续不同 | 带宽、限速、插补或驱动动态 | 匹配 control rate、速度/加速度/jerk 限制；必要时加入有界一阶响应模型 | 用固定 position offset 掩盖动态 |
| 正负方向的 `t90`、超调或稳态不同 | 摩擦、迟滞、背隙相关动态 | 以方向、速度、反转、hold 为条件的状态模型；先限于有效域 | 只根据上一个名义目标永久补偿 |
| 重复曲线均值接近但标准差/分位数大 | 通信/测量/执行随机抖动 | observation/action jitter、丢帧与参数随机化；评估鲁棒策略 | 把单次曲线拟合成确定性 delay |
| 超调、振荡或接近限位才恶化 | 控制增益、饱和、重力/负载 | drive 力矩/速度饱和、阻尼、质量惯量和 payload 分层建模 | 在未核对 mapping/limit 前改比例项 |

动态配置必须与静态配置分离。例如每轴保存 `command_delay_s`、`observation_delay_s`、`control_rate_hz`、`velocity_limit`、`acceleration_limit`、`jitter_distribution`、有效位置/速度/负载域和证据 hash。缺失项显式为 `not_identified`，不得填零冒充已测。

`Δt = t_real - t_isaac` 的符号决定修复方向。若 `Δt90 < 0` 且其绝对值远大于 `Δt_onset`，说明 Isaac 到达稳态比真机慢；应在 Isaac-only 环境调 drive 闭环带宽、control rate、速度/加速度限制或一阶响应，**不能**添加 delay FIFO。只有 Isaac 比真机快且曲线近似整体平移时，command/observation FIFO 才是候选。

在调 drive 前，bridge 必须记录 `command_received → target_applied → first_physics_response → state_published` 四段时间。只有 `target_applied → first_physics_response` 仍明显慢时，才可将问题归于 drive/physics；否则先修 bridge 或 state publisher。

## 验证与提升规则

1. 前两次重复拟合，第三次仅用于 `within_session_holdout`。
2. 动态候选要同时改善留出曲线的 `Δt_onset`、`Δt90` 或曲线误差，并不增加稳态位置误差。
3. 用未参与拟合的另一幅值或低幅 ramp 复验；只对阶跃有效的模型不得声称普适。
4. 再做一次独立上电/session 的真实验证，才可作为长期默认配置。
5. 任一超出有效位置、速度、payload、温度或控制周期域的命令，动态层必须透传或回退至已测随机化范围。

## 交付物

- 每轴原始时间序列和 receipt；
- `dynamic_metrics.json`：质量 gate、t_onset/t10/t50/t90/t95、峰值速度、超调、重复统计；
- `openarm_isaac_dynamic_replay_candidate_v1.json`：候选项、有效域、证据 hash、验证状态；
- held-out 和独立 session 验证报告；
- 更新后的 scene/bridge 配置指纹与 integration ledger。

## 当前可复用实现

- `measure_real_sim_dynamic_identification.py`：受限的原始记录器。它不会启动 router 或使能电机；只有已获授权的 real-enabled router 存在时，canonical command 才可能到达真机。
- `analyze_dynamic_gap.py`：纯离线分析器；从原始 JSON 输出每个 phase 的归一化时序指标和分类候选。
- `manifests/right_j7_dynamic_pilot_v1.yaml`：第一个单轴 pilot 的审查定义，仍未授权、未执行。

先用合成数据和 Isaac-only route 验证记录格式、receipt gate 与分析逻辑；不要把 Isaac-only 结果误报为真机动态标定。
