# OpenArm 14 轴静态 Sim2Real Gap 与 Isaac 修复汇总

更新日期：2026-09-16。本文汇总已完成的关节位置多点辨识与 v3 Isaac compare/replay 验证。它不覆盖动态 delay、相机、坐标系、接触、负载或任务成功率。

## 结论

- 14/14 轴均有可用的同一上电 session 留出 replay 证据，并已写入 v3 的 Isaac-only compare/replay 配置。
- v3 只使 Isaac 的关节位置 replay 更接近本次测得的真机稳态位置；它不改写真机控制器、CAN、USD、URDF 或 drive。
- 留出样本不等于独立 session 验证；长期使用前仍需在另一上电、温度和负载条件下复验。
- 动态 delay、带宽和速度限制尚未识别。此前 J7 墙钟动态试验受到低 RTF 干扰，不能作为调 drive 或加入 delay 的证据。

## 术语和数字如何读

| 术语或数字 | 这里的意思 |
|---|---|
| `v3` | 第 3 版静态标定配置。v1/v2 是此前的候选或中间版本；v3 是当前用于 14 轴 Isaac replay 的版本号，不是机器人硬件版本。 |
| 同一上电 session | 机器人从上电到关机之间的一段连续实验。环境、温度、负载和控制器状态较接近，因此能验证本次拟合是否复现；不能证明换天、重新上电后仍一样。 |
| `within_session_holdout` | 同一上电 session 内，故意不参与拟合的第三次重复轨迹。前两次用于算参数，第三次只用于检查参数有没有“记住训练数据”。 |
| Isaac-only | 只在 Isaac 中发送和验证命令；没有向真机发命令。它验证仿真 bridge 和标定配置能否工作，不能单独证明真机任务成功率。 |
| `+0.05`、`-0.05`、`+0.10` | 相对每轴起始位置的关节位移，单位均为 rad；`0.05 rad` 约为 `2.86°`，`0.10 rad` 约为 `5.73°`。 |
| 标定配置 | 可版本化的 JSON 参数文件，记录每轴的比例、偏置和方向项，供 Isaac bridge 在 replay 时读取；它不是 USD 模型文件，也不写入真机。 |
| `receipt real_sent=false` | bridge 已接收并应用了 Isaac 命令，但这条命令没有发送给真机；这是 Isaac-only 验证的安全边界。 |
| 留出 MAE `0.011820 → 0.000918 rad` | 右 J7 的第三次未参与拟合轨迹中，平均绝对稳态误差由约 `0.68°` 降至约 `0.053°`。这说明 v3 对该次留出轨迹有效；仍不代表长期、动态或接触条件下的精度。 |

## 数据与验证范围

辨识轨迹为每轴从实测起始位置出发，依次移动 `+0.05 rad`、回起点、`-0.05 rad`、回起点、`+0.10 rad`、回起点；采样频率为 50 Hz，每个位置保持 3 s，共做三次。前两次用于拟合，第三次为同一上电 session 的留出验证。J6 来自 v4 补采；J7 使用 v5 独立复验替换 v4 结果。

- v3 标定：[openarm_isaac_replay_calibration_v3.json](calibrations/openarm_isaac_replay_calibration_v3.json)。其顶层字段记录版本、来源文件、适用范围和各关节；每个关节记录 `status`、`classification`、`application_mode`、`emulation(a/b/h)`、残差和 delay 状态。
- 全 14 轴 Isaac-only replay：14/14 通过，所有 receipt `real_sent=false`。每轴 target 与 return 的验收阈值均为 `0.01 rad`；本次最大 target/return error 为 `0.000434/0.000341 rad`，分别仅为阈值的约 4.3% 与 3.4%。结论是“Isaac 能按 v3 的等效目标稳定到位并返回”；不是“真机误差已低至该数值”。
- 右 J7 独立复验的留出 MAE：`0.011820 → 0.000918 rad`。

## 参数含义

| 字段 | 含义 | 使用边界 |
|---|---|---|
| `a` | Isaac replay 目标的幅值比例项。例如 `a=0.83` 时，名义目标变化 `0.10 rad` 会先映射为约 `0.083 rad`，再叠加 `b` 与方向项。它表示本次数据中的经验映射，不等于“机械臂实际传动比就是 0.83”。 | `a` 偏离 1 时必须审计单位、轴方向、传动比、限位与 drive target 语义，不能直接认定为机械传动错误。 |
| `b` | 不随方向变化的静态位置项 | 仅在当前测得的关节位置、控制周期、负载和温度域内适用。 |
| `h+ / h−` | 正向/负向接近的方向项 | 近似迟滞/摩擦/背隙；当前只按前一 nominal target 判断方向。 |
| 残差 std | 该模型未解释的稳态离散度 | 应用于随机化范围或进一步分层采样，不应被强行固定补偿。 |
| 留出 MAE | 第三次重复的 raw 与 emulated 比较 | 是同 session 证据，不能代表长期真机精度。 |

### 表格怎么读，能得出什么结论

左右臂表每一行只描述一个关节在当前静态测量范围内的经验映射。`已识别静态类型`是数据形状提示，不是已经证实的机械故障；`a/b/h`共同决定 Isaac replay 的等效目标；`残差 std`表示同一模型还解释不了的离散部分；最后一列说明当前允许的 Isaac 使用方式。

例如左 J1 的 `a=0.831852` 表示该轴的名义位置变化在 Isaac replay 中需要先按约 0.832 倍映射；同时正、负方向有不同的附加项，因此正反向接近同一点时目标会略有不同。这个结果支持“在本次范围内使用状态化 replay”，但仍要求审计关节名、单位、轴方向、传动和限位，不能仅凭 `a≠1` 判定硬件有问题。

`emulated` 指“经过 `a/b/h` 映射后实际发给 Isaac 的等效目标”。`raw` 指未映射的名义目标或原始测量值。留出 MAE 的 `raw → emulated` 下降，表示用等效目标后，Isaac 输出更接近本次测得的真机稳态位置；它不表示真机本身被修改了。

### 验证状态的判定标准

| 当前状态 | 判定依据 | 代表的结论 |
|---|---|---|
| 14 轴 Isaac compare/replay：已通过 | 14 个关节均有 target/return 记录；每项绝对误差不超过 `0.01 rad`；receipt 全部为 `real_sent=false` | 配置和 Isaac bridge 的静态 replay 验证通过。 |
| 真机独立 session 稳态复验：未完成 | 尚无另一上电、温度或负载条件下的同协议留出轨迹 | 不能宣称长期稳定。 |
| 动态 delay/带宽：未完成 | 缺少 RTF≥0.95 条件下的真机—Isaac physics-time 曲线和留出验证 | 不能写入动态 FIFO、drive 或控制率配置。 |
| 映射审计：部分待完成 | `a≠1` 的轴尚未逐项确认 joint 名、单位、符号、传动、限位和电机 profile | 静态 replay 可用于当前实验，根因仍待确认。 |

## 左臂

| 轴 | 已识别静态类型 | `a` | `b` rad | `h+ / h−` rad | 残差 std rad | 留出 MAE raw → replay rad | Isaac 修复 |
|---|---|---:|---:|---:|---:|---:|---|
| L J1 | 比例/传动候选；方向迟滞/摩擦候选 | 0.831852 | 0.000508 | -0.001014 / 0.000167 | 0.002517 | 0.006975 → 0.001441 | 先映射审计，再方向状态 replay |
| L J2 | 比例/传动候选 | 0.859110 | -0.000202 | -0.002090 / -0.001744 | 0.001610 | 0.006139 → 0.001735 | 先映射审计，再方向状态 replay |
| L J3 | 比例/传动候选；方向迟滞/摩擦候选 | 0.962372 | -0.013062 | 0.002502 / 0.019378 | 0.003312 | 0.010047 → 0.002744 | 先映射审计，再方向状态 replay |
| L J4 | 静态偏置候选；比例/传动候选 | 0.925537 | -0.002011 | 0.005095 / 0.004044 | 0.000333 | 0.003370 → 0.000496 | 先映射审计，再方向状态 replay |
| L J5 | 方向迟滞/摩擦候选 | 0.985442 | -0.014942 | 0.001410 / 0.026547 | 0.002749 | 0.012016 → 0.002912 | 方向状态 replay |
| L J6 | 方向迟滞/摩擦候选 | 0.985701 | -0.018906 | 0.001858 / 0.025268 | 0.002273 | 0.011753 → 0.001637 | 方向状态 replay |
| L J7 | 比例/传动候选；方向迟滞/摩擦候选 | 0.917870 | -0.002845 | -0.002771 / 0.017791 | 0.000951 | 0.012543 → 0.000796 | 先映射审计，再方向状态 replay |

## 右臂

| 轴 | 已识别静态类型 | `a` | `b` rad | `h+ / h−` rad | 残差 std rad | 留出 MAE raw → replay rad | Isaac 修复 |
|---|---|---:|---:|---:|---:|---:|---|
| R J1 | 比例/传动候选 | 0.870867 | 0.002795 | -0.001204 / 0.000362 | 0.000763 | 0.005224 → 0.000583 | 先映射审计，再方向状态 replay |
| R J2 | 比例/传动候选 | 0.847096 | -0.003824 | 0.003005 / 0.002464 | 0.000888 | 0.005673 → 0.000707 | 先映射审计，再方向状态 replay |
| R J3 | 静态偏置候选 | 0.990905 | -0.001007 | -0.000114 / 0.002061 | 0.000597 | 0.001330 → 0.000483 | 静态 compare/replay |
| R J4 | 比例/传动候选；方向迟滞/摩擦候选 | 0.915375 | -0.003397 | 0.005347 / 0.008875 | 0.000249 | 0.005066 → 0.000233 | 先映射审计，再方向状态 replay |
| R J5 | 方向迟滞/摩擦候选 | 0.980738 | -0.012201 | -0.003233 / 0.025842 | 0.000131 | 0.014556 → 0.000128 | 方向状态 replay |
| R J6 | 比例/传动候选；方向迟滞/摩擦候选 | 0.932221 | -0.010461 | -0.000127 / 0.023906 | 0.001676 | 0.013555 → 0.001351 | 先映射审计，再方向状态 replay |
| R J7 | 方向迟滞/摩擦候选 | 0.998663 | -0.021953 | 0.001227 / 0.024116 | 0.001213 | 0.011820 → 0.000918 | 方向状态 replay |

## 按误差类型采取的修复

### 1. 静态偏置候选

右 J3 是主要的静态 compare/replay 候选；左 J4 同时含静态和比例证据。修复通过 v3 bridge 将 nominal target 变为等效 Isaac target，目标是让仿真输出接近测得真机输出。该项不回写真机。

### 2. 比例/传动候选

左 J1/J2/J3/J4/J7、右 J1/J2/J4/J6 的 `a` 明显偏离 1。当前 v3 已用其做 Isaac replay，但每个比例项仍须完成 ROS joint 名、rad/deg、轴符号、传动比、关节限位、USD drive target 与电机 profile 的 mapping audit。审计失败时先修映射，不应用数学拟合掩盖配置错误。

### 3. 方向迟滞/摩擦候选

左 J1/J3/J5/J6/J7、右 J4/J5/J6/J7 使用正负接近方向项。J5/J6/J7 的负方向项约为 `0.024–0.026 rad`，说明回程方向对稳态结果影响明显。v3 的 bridge 使用 stateful replay；后续应记录真实反馈方向、速度、反转、hold 和零交叉，决定是否升级为摩擦/死区/背隙模型或随机化。

### 4. 随机残差

残差 std 是未被当前静态模型解释的部分。它不应写成固定 offset；训练时应将其按关节、方向、位置和负载分层，形成 encoder/actuator noise 或参数随机化范围。

### 5. 动态 gap

静态 endpoint 不能估计 delay。J7 原始同目标动态 pilot 已采到 receipt 与曲线，但采集期间 Isaac 的 PhysX RTF 约为 `0.27`，墙钟 `t90` 被仿真吞吐拖慢。因此当时的 `real−Isaac t90` 仅保留为性能异常证据，动态 delay、带宽和 drive 参数均为 `not_identified`。下一步需先在保留 RL 相机的条件下把 RTF 提升并稳定至至少 `0.95`，再关闭静态 replay、重采同一真机—Isaac 动态曲线，并按单因素验证 drive、控制率或速度限制。详见 [动态协议](dynamic_gap_protocol_zh.md)。

## 验证状态与未完成项

| 项目 | 当前状态 | 通过判据 | 下一步 |
|---|---|---|---|
| 14 轴 Isaac compare/replay | 已通过（仅 Isaac） | 14 个关节各有 target 与 return 记录；两项绝对误差均 `≤0.01 rad`；所有 receipt 为 accepted 且 `real_sent=false`。本次最大误差为 `0.000434/0.000341 rad`。 | 记录跨主机配置 SHA-256，保留 v3 版本化文件。 |
| 真机独立 session 稳态复验 | 未完成 | 重新上电后不重新拟合 v3，按同一协议采第三次留出轨迹；每轴 replay 后稳态误差应在任务容差内，且不得出现新的方向反转、限位或持续漂移。当前建议以 `≤0.01 rad` 作为关节级筛查门槛，再由任务末端误差确认。 | 尤其 J6/J7；验证温度、上电、负载和不同位置域漂移。 |
| 动态 delay/带宽 | 未完成 | 先满足 physics RTF `≥0.95`；至少有 8 条有效的真机—Isaac physics-time 阶跃及 `t90`；前两次拟合、第三次留出和另一幅值/ramp 均改善曲线指标，且不增加稳态误差；最后通过独立上电 session。 | 先提升 RTF，再单轴 pilot，之后才做 14 轴动态采集。 |
| 映射审计 | 部分待完成 | 每个 `a≠1` 的轴均有 ROS joint 名、Isaac DOF、单位、正方向、传动、限位、USD drive target 和电机 profile 的一致性记录。 | 对所有 `a≠1` 的轴完成审计。 |
| 机器人几何、TCP、相机、桌面、接触与抓取 | 未完成 | 每层均有独立的真实测量、Isaac 对照和任务容差；关节位置 replay 不能替代这些验收。 | 按全栈 gap 覆盖文档分层标定与任务级验证。 |
| 真实任务成功率 | 未完成 | 在固定任务、相同初始状态分布和足够重复次数下，静态 replay/动态层/随机化策略相对 nominal 的末端误差与成功率有可复现改善，并在独立 session 保持。 | 比较 nominal、静态 replay、动态 replay、随机化策略的末端误差、接触与成功率。 |

## 相关文件

- [静态标定配置](calibrations/openarm_isaac_replay_calibration_v3.json)
- [12 轴主辨识候选](results/openarm_real_sim_bimanual_offset_identification_v3/gap_model_candidates.json)
- [J6/J7 补采候选](results/openarm_real_sim_right_j6_j7_offset_identification_retry_v4/gap_model_candidates.json)
- [J7 独立复验候选](results/openarm_real_sim_right_j7_offset_independent_replay_v5/gap_model_candidates.json)
- [全轴 Isaac-only 验收](results/sim_only_compensated_replay_v3_full14/full14_summary.json)
- [动态协议](dynamic_gap_protocol_zh.md)
- [完整全栈 gap 范围](sim2real_gap_coverage_zh.md)

## 2026-09-17 独立上电复测：v2 执行结果

`openarm_static_independent_session_v2` 使用冻结的 v3 配置
`660bce671fb68463ffe1925a9b603edf879586412edc508145d5c1e045a745ba` 完成。
真实控制栈以 `OPENARM_SKIP_RETURN_TO_ZERO=1` 从测得姿态保持启动；每轴执行预注册的正负小幅稳态轨迹并回到该轴测得起点。v1 在左 J1 中止，原因是 recorder 错将 replay 的 nominal target 作为 Isaac tracking gate；v2 已改为按同一方向状态机计算 `emulated target`。

- 14 轴均完成；J1--J3/J5--J7 各 18 个 waypoint，J4 各 15 个 waypoint，共 246 个。
- 全部运行协议 gate 通过，记录 717 条 accepted router receipt；临时真实 router 已退出。
- Isaac 相对 emulated target 的最大跟踪误差为 `0.008033 rad`，低于本试验的 `0.01 rad` Isaac tracking gate。
- 但 v3 **尚不能标为** `independent_session_validated`：本次为 replay-on 验证，未同时采集 replay-off 的 raw 基线；并且稳态 `Isaac emulated − real` 最大绝对误差为 `0.026671 rad`（右 J5），右 J7 为 `0.015247 rad`，高于可作为关节筛查参考的 `0.01 rad`。

因此该 session 的正确状态是 `measured`：它证明 CAN 恢复、无回零保持、真实受限路由、v3 emulated tracking 与完整数据记录可运行；它不证明 v3 跨上电泛化通过。后续应在新的具名试验中先采同条件 replay-off raw 基线，再用冻结 replay-on 进行配对比较，并优先审计右 J5/J7 的有效域、方向项、映射与控制 profile。

证据文件：[v2 汇总](results/openarm_static_independent_session_v2/independent_session_validation.json)，各轴原始状态与回执在同目录的 `openarm_*_joint*.json`。

## 2026-09-17 右 J5 v4 独立上电留出验证

冻结的右 J5 v4 Isaac replay 候选
`e7ef68849b6d737ceea2dc45b783a9db33bbc258a818abc40ac82ac07d79cf68`
在 `openarm_right_j5_v4_independent_power_holdout_v2` 通过。真机始终接收 canonical nominal target；只有 Isaac replay 使用 v4。18 个 waypoint 均有完整 state/receipt，router 在试验后退出并回到测得起点。

- raw nominal→真机 MAE：`0.011187 rad`；v4 Isaac emulated→真机 MAE：`0.001718 rad`。
- 最大 emulated→真机配对误差：`0.002156 rad`；Isaac tracking 最大误差：`0.001588 rad`。
- 预注册 gate 均通过，因此右 J5 条目状态为 `independent_session_validated`。

该结果只提升右 J5；它不是 14 轴统一发布包，也不允许修改真机、CAN、基础 USD 或 URDF。不可变证据包见 [右 J5 v4 独立上电包](calibration_packages/openarm_isaac_replay_v4_right_j5_independent_power_v2/package_manifest.json)，其中保留候选、manifest、raw 数据、preflight、router/trial log 与 SHA-256。
