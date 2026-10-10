# OpenArm 标定生命周期：同一上电、独立上电与动态推广

本规则用于 OpenArm 的静态关节 replay、独立上电复验、动态识别、有效域/随机残差和映射审计。它不授权任何真机动作；任何会到达真机的采样仍需单独的命名授权、清场、急停、回程和单一命令源确认。

## 1. 不变原则

1. 所有参数必须按关节名保存，单位为 rad、rad/s、kg、°C、Hz 或 s；禁止以数组下标推断关节。
2. 静态、动态、映射和随机化是不同层：不得用静态 endpoint 拟合 delay，不得用低 RTF 的墙钟曲线调 drive，不得用随机波动写成固定偏置。
3. 基础 USD、URDF、真机 CAN 和真机控制器保持不改写。所有候选先进入独立、版本化的 Isaac replay/override 或训练随机化层。
4. 参数只在已记录的有效域内使用。越界时透传名义目标或使用已测随机化范围，并记录缺口；不能静默外推。
5. 每次测量、拟合、部署、拒绝和回退都更新项目 evidence/ledger；规则变化也须记录版本、原因、证据和影响范围。更新规则不能追溯性把历史未通过数据改为“通过”。

## 2. 证据与状态名称

使用以下固定状态，避免“已标定”含义不清：

| 状态 | 含义 | 能做什么 |
|---|---|---|
| `measured` | 原始数据、receipt、状态和条件完整，但尚未拟合 | 离线分析 |
| `within_session_candidate` | 同一上电 session 前两次拟合、第三次留出通过 | Isaac-only compare/replay 候选 |
| `independent_session_validated` | 重新上电后，用冻结参数通过预注册验证 | 可作为当前有效域内的默认 Isaac replay 候选 |
| `dynamic_candidate` | RTF 合格且 physics-time 动态留出通过 | Isaac-only 动态 override 候选 |
| `task_validated` | 在预注册任务集和独立真实 session 改善任务指标 | 可用于该任务的推荐配置 |
| `not_identified` | 数据、时间基准或门槛不足 | 不填零，不应用固定补偿 |
| `invalid` | receipt/state/安全/时间基准失败 | 只保留诊断，不用于拟合 |

## 3. 同一上电 session：保留但不越级

同一上电 session 是一次开机到关机间连续实验。其目的不是证明长期稳定，而是防止模型只记住前两次数据。

每个关节、每个静态条件组合的最小规则：

1. 从测得安全起点执行预注册的正向、负向和另一幅值稳态轨迹。
2. 前两次重复仅用于拟合 `a`、`b`、`h(direction)`；第三次重复必须冻结参数并作为 `within_session_holdout`。
3. 保存起点、方向、目标、保持时间、采样率、payload、温度、控制率、所有 receipt 和状态窗口。
4. 同一上电留出通过，只能将条目标为 `within_session_candidate`；不允许因此称为长期真机标定。

静态 Isaac-only replay 的工程验收还需：每轴 target/return 记录完整、误差不超过本试验声明的阈值、receipt accepted 且 `real_sent=false`。这证明 bridge 与配置，不证明真机泛化。

## 4. 独立上电 session：冻结参数的泛化验证

独立上电 session 必须在真机关机后重新上电，并记录开机时间、固件/profile、环境温度、payload、初始姿态、控制频率和标定文件 SHA-256。

规则：

1. 不得使用新数据重拟合或手工修改待验证的静态参数；固定已有标定文件版本。
2. 使用与同一上电阶段相同的安全轨迹，至少覆盖每轴正向、负向和另一幅值；J6/J7 优先，但最终目标是 14 轴。
3. 分别报告 raw nominal 和 emulated Isaac replay 相对真机的稳态 MAE、最大误差、方向差和回程误差。
4. 预先声明每轴/任务容差。若尚无任务容差，可用 `0.01 rad` 仅作为关节级筛查门；不得把筛查门称为任务成功标准。
5. 通过要求：冻结的 emulated 结果在留出轨迹上满足预注册容差，优于或不劣于 raw 基线，没有新的限位、方向反转、持续漂移或安全异常。
6. 失败或漂移时保留原文件和数据，标为 `invalid` 或域外；新建候选版本，不能覆盖已验证版本。

## 5. 动态识别和修复

### 5.1 进入条件

动态实验前必须同时满足：

- Isaac PhysX RTF 在保留 RL 必需相机、关闭仅供查看的 active viewport 条件下达到并稳定在 `>=0.95`；记录 probe JSON。
- Isaac timeline/physics 正在推进，bridge、state publisher 和 receipt 可见。
- 原始真机—Isaac 对比关闭静态 replay，使两端接收同一 canonical nominal target。
- 真机动态 manifest 获得单独命名授权；它声明关节、最大幅值、速率、保持、回程、次数、abort gate 与现场安全确认。

### 5.2 最小采样

先做单轴受限 pilot，再扩展到全轴。每个 waypoint 保存 command published、accepted receipt、target applied、first physics response、state published、真机/Isaac feedback 的同一记录机单调时间。

对每一侧独立计算：

```text
q0     = 命令前稳定窗口中位数
q_inf  = 命令后稳定窗口中位数
r(t)   = (q(t) - q0) / (q_inf - q0)
```

随后比较 onset、t10/t50/t90/t95、settling、峰值速度、超调和方向差。动态候选只能依据 physics-time 指标分类；墙钟结果仅作运行性能诊断。

- 近似整体平移且形状一致：候选为 command/observation delay。
- onset 接近、rise/peak/t90 不同：候选为带宽、控制率、速度/加速度限制或 drive。
- 正负向曲线不同：候选为摩擦、迟滞或背隙动态。
- 重复方差大、均值稳定：候选为 jitter/randomization。

一次只扫一个因素。每个候选须通过第三次同一上电留出、另一幅值或低幅 ramp、独立上电验证；改善 timing/curve 指标且不增加稳态误差，才标为 `dynamic_candidate`。动态项只可写入 Isaac 的版本化 override，绝不写入真机路径。

## 6. 有效域与随机残差

### 6.1 分层采样设计

按关节分别建立条件表，至少包含：位置区间、方向、速度档、payload、温度和控制频率。每个条件组合做至少三次重复，并保存条件标签。

推荐渐进顺序：空载、低速、小幅、中心位置开始；一次仅扩展一个维度。真机采集仍以预注册安全范围和独立授权为前提。

### 6.2 残差计算和区分

对每个样本计算：

```text
residual = measured_feedback - model_prediction
```

- 残差均值随位置、方向、速度、payload 或温度稳定改变：是系统性条件项，新增分段/条件模型后重新做留出验证。
- 同一条件内残差均值接近零，而标准差、p95 或分布宽度较大：是随机残差，保存其分布供 domain randomization。
- 只在未采样条件中出现：属于域外，不用现有参数解释。

随机化配置必须引用原始数据与分箱统计，保存均值、std、p05/p95、样本数、关节和条件。它不得改变真机命令。

## 7. 映射审计

所有 `a != 1` 或出现异常方向项的关节，在进入长期默认前必须建立一条可审计记录，至少包含：

- ROS joint 名、Isaac articulation DOF 名和索引；
- rad/deg 单位及命令、状态、USD drive target 的单位；
- 正方向、joint axis、joint origin、左右臂镜像关系；
- 传动/减速比、软硬限位、额定速度/力矩；
- USD drive type、stiffness、damping、max force、速度限制；
- 真机 controller/profile/firmware 版本；
- 证据文件、检查日期和审计结论。

审计发现映射错误时，先修映射并重新采集；不得用 `a/b/h` 继续掩盖错误。审计未完成的条目只能保留为当前域内的 Isaac replay 候选。

## 8. 修复、回退与规则维护

1. 每个拟合或修复创建新版本，不覆盖旧 JSON/override；保留 source data、代码版本、场景 hash、参数 diff、评估和 SHA-256。
2. 改动前记录 baseline；改动后执行同一 Isaac-only 验收，再执行所需留出/独立验证。
3. 任一安全、receipt、state、RTF 或有效域 gate 失败时立即停止提升；配置回退到上一个 `validated` 版本，失败数据标记 `invalid`。
4. 每次新增证据都检查既有规则是否仍适用：若发现阈值、有效域或分类规则不再覆盖数据，提出版本化规则变更，说明原因、影响的旧配置和迁移/回退方案；未经留出验证不得将新规则设为默认。
5. 在项目 ledger 中记录“规则版本 → 证据 → 决策 → 配置版本 → 验证结果”的链路，使后续 agent 可以继续更新，但不能在没有证据时扩大适用范围。

## 9. 动态标定前必须完成的三项工作

当真机与 Isaac 分开运行、尚未建立可信共同时间基准或 PhysX RTF 未达标时，暂停跨端 delay/t90 拟合，优先按以下顺序完成静态泛化、映射审计和有效域工作。三项完成后仍将动态 delay 保持为 `not_identified`；不得添加 command/observation FIFO。

### 9.1 独立上电静态位置复验（优先级 1）

**目的**：验证冻结的 v3 `a/b/h(direction)` 能否跨重新上电复现真机稳态位置，而不是用新数据再次拟合。

**前置条件**：

- 记录待验证 calibration JSON 的 SHA-256；禁止编辑参数。
- 具名真实试验授权明确包含 `openarm_static_independent_session_v1`、14 轴、最大位移、保持/回程、次数与 abort 条件。
- 真机安全 gate、唯一命令源、receipt 和 state freshness 全部通过。

**每轴最小协议**：从实测安全起点，按正向、负向和另一幅值执行预注册的小幅稳态轨迹；每个 target 保持至稳态并自动回程。每个条件至少三次：前两次仅用于记录稳定性，第三次为本次 session 的留出。真机与 Isaac 分开运行时，分别记录各自稳态位置；不计算跨端墙钟 delay。

**离线比较**：对冻结参数同时计算 raw nominal Isaac 结果与 emulated Isaac 结果相对真机的 MAE、最大误差、正负方向误差和回程误差。

**通过/回退**：预先声明任务容差；若没有任务容差，`0.01 rad` 仅作关节筛查。emulated 必须满足容差，并优于或不劣于 raw，且不能出现限位、方向反转、持续漂移、receipt/state 缺失。通过后将条目标为 `independent_session_validated`；失败时保留 v3 和原始数据，新建候选版本，不覆盖旧版本。

**产物**：冻结配置 hash、manifest、真机状态/receipt、Isaac replay 结果、每轴 metrics、比较摘要和验证结论。

### 9.2 映射审计（优先级 2）

**目的**：解释或排除 `a≠1` 的实现/模型原因，防止把 joint 名、单位、轴符号、限位或 drive 语义错误伪装为标定参数。

**范围**：所有 `a≠1` 轴必须逐轴完成；按风险优先审计偏离最大的轴和所有带方向项的轴。

**每轴检查清单**：

1. ROS joint 名、真机反馈名、Isaac articulation DOF 名和索引一一对应。
2. 命令、状态、日志与 USD drive target 都使用 rad，或存在明确可复现的 rad/deg 转换。
3. 正方向与 joint axis、joint origin、左右臂镜像关系一致。
4. URDF/USD/真机 profile 的传动或减速比、软硬限位、速度和力矩限制一致。
5. USD angular drive 的 type、target position、target velocity、stiffness、damping、max force 与当前实验配置已记录。
6. 真机 controller、固件和电机 profile 版本与采样 evidence 绑定。

**判定**：全部证据一致则标为 `mapping_audited`；发现错误则先修映射、保留审计前结果为 `invalid_for_promotion`，再从同一安全协议重采。未知或无法读取的字段不等于一致，保持 `mapping_pending`。

**产物**：每轴一条 mapping audit record，包含来源文件/路径、版本/hash、检查日期、结论、发现项与复测链接。

### 9.3 有效域与随机残差（优先级 3）

**目的**：说明静态 replay 在什么条件下可靠，并把不可预测的剩余差异转成训练随机化，而不是固定补偿。

**渐进采样矩阵**：每次只增加一个条件维度。基线为中心安全位置、空载、慢速、一个方向；随后逐步覆盖位置区间、正负方向、速度档、payload、温度和控制频率。所有真实采样的上限、次数和回程必须写入具名 manifest。

**每个条件组合的记录**：joint、起点/目标、方向、位置 bin、速度 bin、payload、温度、控制 Hz、真机 profile、状态/receipt、稳态窗口和三次重复。

**统计**：冻结当前模型，计算 `residual = measured_feedback - model_prediction`。按条件 bin 保存样本数、均值、std、p05、p95、最大绝对值和方向差。

**区分与修复**：

- 条件内残差均值显著且跨重复稳定：新增可解释条件项，重新做同一上电留出和独立上电复验。
- 条件内均值接近零、散布较大且无稳定趋势：生成有界随机化分布；随机化只进入 Isaac 训练/评估。
- 新条件没有数据：标为 `out_of_domain`，透传名义目标或使用已测保守随机化，禁止外推静态补偿。

**通过条件**：每个声明的有效域 bin 均有足够重复、第三次留出不恶化、分布统计完整；对外只声明已覆盖的条件组合。未覆盖 payload/温度/速度不是“零影响”，而是未验证。

**产物**：条件矩阵、原始数据索引、每轴 residual 分布 JSON、有效域配置、随机化配置、留出/独立 session 报告与训练使用的版本 hash。
