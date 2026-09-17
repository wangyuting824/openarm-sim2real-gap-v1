# OpenArm 本体：结构、控制与 Sim2Real 对齐总览

更新日期：2026-09-16。本文只汇总 OpenArm v2.0/v20 本体的运动学、关节状态、控制接口、静态关节对齐、动态响应与 Isaac 运行条件。物体、桌面、接触、任务相机标定、视觉数据集和双臂任务协同不在本文范围。

## 1. 当前结论

OpenArm 本体的静态关节位置对齐已完成：左右臂共 14 个转动关节均有同一上电 session 的留出验证，v3 Isaac compare/replay 对全部 14 轴通过。该修复只作用于 Isaac 的 replay/训练层，不改写真机控制器、CAN、基础 USD 或 URDF。

动态层尚未形成可写入配置的本体参数。右 J7 的真机—Isaac 配对试验曾显示 Isaac 的墙钟响应较慢，但此时 Isaac 的 PhysX 实时倍率仅约 0.27；后续 A/B 证明主要原因是 GUI/RTX 渲染阻塞物理推进。因此不能把那组墙钟 `t90` 当作 J7 drive 过软的证据，也不能据此修改 USD drive、速度限制或控制器增益。

本体下一阶段的有效顺序是：先使 Isaac 的物理推进稳定接近实时，再按 physics-time 复测各关节动态曲线；最后才决定是否建立每轴独立的动态 override layer。

## 2. 本体配置与关节约定

| 项目 | 当前约定 | 状态 |
| --- | --- | --- |
| 机器人版本 | `openarm_v2.0` / `v20` | 已统一用于 ROS/URDF/Isaac 对齐 |
| 本体自由度 | 左右各 7 个转动关节，共 14 个；另有左右各 2 个 finger，共 18 DOF 状态 | 已测得 Isaac articulation 输出 |
| 关节状态顺序 | `left_J1,right_J1,...,left_J7,right_J7,left_finger_1,left_finger_2,right_finger_1,right_finger_2` | 已验证；所有数据必须保存关节名，不能只依赖数组下标 |
| 角度单位 | rad | 已采用 |
| 本体根节点 | `openarm_body_link0` | 用于本体坐标与世界坐标连接 |
| 双臂基座关系 | `world → openarm_body_link0 → left/right_base_link` | 几何对齐仍需独立验收 |
| 末端链 | `link6 → ee_base_link → joint7/夹爪` | TCP 与夹爪几何仍需任务级复验 |

### 运动学必须独立验收的项目

每轴应在安全小幅范围内检查零位、正方向、转轴、joint origin、连杆几何和限位。若某关节后所有下游连杆姿态都错，应先查该关节的 axis/origin/zero；若整条臂整体平移或朝向错误，应先查 body 与左右 base 的静态变换。坐标、单位、方向或限位未确认前，不应用数值 replay 去掩盖模型错误。

## 3. Isaac 本体状态与命令链路

| 链路 | 当前实现 | 已验证边界 |
| --- | --- | --- |
| 仿真状态 | `/sim/openarm/joint_states`，发布 name、position、velocity | 可获得 18 DOF；`effort=[]`，不能作为力/扭矩或接触证据 |
| 受控命令输入 | `/sim/openarm/timestamped_joint_command` | 只控制当前 Isaac articulation，不访问 CAN、USB 或真机 controller |
| 命令回执 | `/sim/openarm/command_receipt` | 用于确认命令被 bridge 接收；动态对齐必须同时保存 command、receipt 和 state |
| 本体控制方式 | bridge 在每个 Isaac update 持续施加当前 position target | 仅代表当前仿真控制语义，不等同真机控制周期 |
| 静止保持基线 | `simulator_position_target_each_update` | 18 DOF position/velocity 标准差均为 0；这是确定性硬保持，不能当作真机噪声或自然被动动力学 |

ROS state 的约 40 Hz 消息吞吐是发布/录包结果，不是 PhysX dt、关节 drive 更新率或真机控制频率。动态分析必须保留实际 PhysX step 时间和每条 command 的 receipt、target applied、first physics response、state published 时间点。

## 4. 已验证的静态关节对齐

### 4.1 模型与证据边界

静态 v3 使用：

```text
q_emulated = a × q_nominal + b + h(direction)
```

其中 `a` 为比例/传动候选，`b` 为静态偏置候选，`h(direction)` 为按接近方向区分的迟滞/摩擦候选。辨识轨迹为每轴在测得起点附近进行 `+0.05`、`-0.05`、`+0.10 rad` 的稳态往返；前两次重复拟合，第三次为同 session 留出验证。

全 14 轴 Isaac-only replay 已通过；最大 target error 为 `0.000434 rad`，最大 return error 为 `0.000341 rad`，且所有 receipt 均标记 `real_sent=false`。这证明 v3 在当前有效域内可复现已测的稳态关节响应，不证明跨温度、上电状态、负载、速度或任务接触的长期精度。

### 4.2 v3 关节参数摘要

| 轴 | `a` | `b` rad | `h+ / h−` rad | 留出 MAE：raw → replay rad | 当前解释 |
| --- | ---: | ---: | ---: | ---: | --- |
| L J1 | 0.831852 | 0.000508 | -0.001014 / 0.000167 | 0.006975 → 0.001441 | 比例/方向候选 |
| L J2 | 0.859110 | -0.000202 | -0.002090 / -0.001744 | 0.006139 → 0.001735 | 比例候选 |
| L J3 | 0.962372 | -0.013062 | 0.002502 / 0.019378 | 0.010047 → 0.002744 | 比例/方向候选 |
| L J4 | 0.925537 | -0.002011 | 0.005095 / 0.004044 | 0.003370 → 0.000496 | 偏置/比例/方向候选 |
| L J5 | 0.985442 | -0.014942 | 0.001410 / 0.026547 | 0.012016 → 0.002912 | 方向候选 |
| L J6 | 0.985701 | -0.018906 | 0.001858 / 0.025268 | 0.011753 → 0.001637 | 方向候选 |
| L J7 | 0.917870 | -0.002845 | -0.002771 / 0.017791 | 0.012543 → 0.000796 | 比例/方向候选 |
| R J1 | 0.870867 | 0.002795 | -0.001204 / 0.000362 | 0.005224 → 0.000583 | 比例候选 |
| R J2 | 0.847096 | -0.003824 | 0.003005 / 0.002464 | 0.005673 → 0.000707 | 比例候选 |
| R J3 | 0.990905 | -0.001007 | -0.000114 / 0.002061 | 0.001330 → 0.000483 | 偏置候选 |
| R J4 | 0.915375 | -0.003397 | 0.005347 / 0.008875 | 0.005066 → 0.000233 | 比例/方向候选 |
| R J5 | 0.980738 | -0.012201 | -0.003233 / 0.025842 | 0.014556 → 0.000128 | 方向候选 |
| R J6 | 0.932221 | -0.010461 | -0.000127 / 0.023906 | 0.013555 → 0.001351 | 比例/方向候选 |
| R J7 | 0.998663 | -0.021953 | 0.001227 / 0.024116 | 0.011820 → 0.000918 | 方向候选 |

`a` 显著偏离 1 的关节必须继续审计 joint 名称、rad/deg、轴符号、传动比、限位、USD drive target 语义和电机 profile。方向项不能直接视作机械背隙；它们目前只是在给定位置域、保持时间与方向历史下的经验模型。残差应进入分层噪声/随机化范围，不应写成固定补偿。

## 5. 动态本体对齐：当前状态与判定规则

### 5.1 当前状态

| 项目 | 状态 | 结论 |
| --- | --- | --- |
| 右 J7 真机—Isaac 原始动态 pilot | 已采到 receipt 与曲线 | 曾观察到 Isaac 墙钟 `t90` 较慢；不能直接归因 drive |
| J7 drive-only 候选 | 已做 Isaac-only 扫描 | 不形成持久化候选 |
| PhysX 120/240 Hz 扫描 | 已完成并恢复快照 | 未改善 J7 墙钟曲线；不能仅靠提高物理频率修复 |
| 全 14 轴 Isaac-only 动态 baseline | 已生成 | 仅为仿真基线，不能推断真机动态 gap |
| 可写入的动态 delay、带宽或 drive 参数 | 未识别 | 必须等待 RTF 合格后的 physics-time 验证 |

J7 配对试验的 wall-time 指标曾给出 `real−Isaac t90` 约 `−0.81 s`。该符号表示当时 Isaac 墙钟下比真机慢；它不表示真机存在额外 delay，也不能支持加入 command FIFO。由于试验期间 PhysX 低于实时，该结果暂时只保留为性能问题的发现证据。

### 5.2 后续动态参数的门槛

1. 原始真机—Isaac 对比必须关闭静态 replay，使双方接收同一 canonical nominal target。
2. 每个 waypoint 以各自的起点 `q0` 和稳态值 `q∞` 归一化，再计算 onset、`t10/t50/t90/t95`、峰值速度、超调和 settling。
3. 时间必须分为 wall-time 与 physics-time；RTF 未接近 1 时，不以 wall-time `t90` 调本体 drive。
4. 同一轴的 drive、速度/加速度限制、control rate、dt/substeps 必须逐类单独扫描，不能同时改。
5. 候选需通过第三次留出重复、另一幅值或 ramp 复验，以及独立上电/负载 session；随后才能写入独立 override/calibration layer，基础 USD 保持不变。

## 6. Isaac 运行性能与本体动态测量的关系

### 6.1 已测结果

| 条件 | PhysX 实时倍率 | PhysX step Hz | Kit update Hz | 结论 |
| --- | ---: | ---: | ---: | --- |
| 正常 GUI | 0.2725 | 16.35 | 24.42 | 物理推进远低于实时 |
| `minFrameRate=15` | 0.2697 | 16.18 | 24.17 | 无实质改善 |
| `minFrameRate=10` | 0.3151 | 18.91 | 22.59 | 仅有限改善 |
| 关闭 active viewport 更新 | 0.6628 | 39.77 | 59.35 | GUI viewport/RTX 为首要负载 |
| headless streaming、时间线已播放 | 0.2633 | 15.80 | 23.70 | `--no-window` 本身没有移除 streaming/RTX 负载；不能当作无渲染基线 |

所有测量中的单个 PhysX step 约为 `16.667 ms`，即 60 Hz dt 仍保持正确；问题是受渲染和主循环负载影响，墙钟时间内无法执行足够多的物理步。因此这不是“USD dt 配错”或“J7 特有 drive 过软”的证据。

### 6.2 本体动态测量规则

- 本体控制、Isaac-only 动态采集和 RL 运行时可关闭仅供人工查看的 active GUI viewport；这不关闭 Replicator 策略相机。
- 视觉 RL 需要的 RenderProduct 必须保留，但应只保留策略实际使用的相机、分辨率、帧率与 annotator；删除未使用的输出。
- 正式实时控制或视觉采集应采用 headless/no-window 运行，并分别记录 RTF、CPU/GPU 负载、相机帧率与策略频率。
- `isaacsim.exp.full.streaming.kit --no-window` 仍可能保留 streaming viewport 与 RTX 管线；必须用 active viewport 关闭 A/B 和 RenderProduct 清单确认实际渲染负载，不能仅凭启动参数认定为无渲染。
- RTF 稳定接近 1 前，本体动态结论只报告 physics-time 指标；不得写入 drive override，也不得将渲染瓶颈拟合为真机 delay。

## 7. 未完成项与执行顺序

| 优先级 | 项目 | 完成条件 |
| --- | --- | --- |
| 1 | 关节映射审计 | 对所有 `a≠1` 的轴完成单位、方向、限位、传动和 USD drive 语义审计 |
| 2 | 运行时性能隔离 | headless 与保留 RL 相机条件下 RTF 接近 1；若未达到，量化 Replicator/RTX 与 CPU/GPU 负载 |
| 3 | 全轴 physics-time 动态基线 | 每轴有 onset、t90、超调、稳态误差及重复统计 |
| 4 | 真机—Isaac 动态复验 | 同一命令、同步时间基准、独立 session 和留出验证均通过 |
| 5 | 本体几何与 TCP 验收 | 左右关节、小范围姿态、base 变换、末端/TCP 与夹爪均通过实物对照 |
| 6 | 接触与负载层 | 建立力/扭矩、负载、摩擦、质量惯量和接触验证；当前 `effort=[]` 不能替代该工作 |

## 8. 权威配置与证据文件

- [静态 14 轴汇总](openarm_static_gap_summary_zh.md)
- [v3 静态 replay 配置](calibrations/openarm_isaac_replay_calibration_v3.json)
- [动态识别协议](dynamic_gap_protocol_zh.md)
- [动态校正运行手册](openarm_dynamic_correction_runbook_zh.md)
- [J7 动态与运行性能过程](isaac_j7_dynamic_tuning_zh.md)
- [Isaac 运行性能诊断](isaac_runtime_performance_diagnosis_zh.md)
- [全栈 Sim2Real 覆盖边界](sim2real_gap_coverage_zh.md)

本文与上述文件的关系是：本文提供本体的单一入口和当前结论；参数原值、原始时间序列和试验过程以链接的版本化配置及 results 文件为准。
