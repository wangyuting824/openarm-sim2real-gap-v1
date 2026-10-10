# OpenArm 静态—动态 Sim2Real Gap 统一工作流

本文件是 OpenArm 本体关节 gap 的唯一决策入口。它把静态位置、映射、有效域/随机残差、运行时性能和动态响应置于同一条证据链中。基础 USD、URDF、真机 CAN 与真机控制器均不在本流程中直接改写。

## 0. 先分清问题层次

| 层 | 要回答的问题 | 数据与结论 |
|---|---|---|
| 静态位置 | 同一名义目标稳态后，Isaac 与真机的位置关系是什么？ | `a/b/h(direction)`；只可作为 Isaac compare/replay 候选 |
| 映射 | 该关系是否其实来自名称、单位、轴、传动、限位或 drive 语义错误？ | `mapping_audited` 或修复后重测 |
| 有效域与残差 | 哪些位置、方向、速度、载荷和温度下模型仍适用？ | 条件分箱、有效域、随机化分布 |
| 运行性能 | Isaac 物理时间能否接近墙钟推进？ | RTF、physics step Hz、Kit update 和渲染/CPU 诊断 |
| 动态响应 | 两端在相同命令下的 onset、t90、峰值速度、超调和 settling 是否不同？ | delay/带宽/drive 候选；只能由合格 physics-time 证据得到 |

静态 endpoint 数据不能辨识 delay；低 RTF 下的墙钟慢速曲线不能辨识 drive；随机散布不能写成固定偏置。

## 1. 安全与运行模式

1. **Health**：只读检查状态流、关节映射、命令/回执端点；无电机上电要求。
2. **Measurement**：真实动作前必须有具名单次授权，并确认电机已上电、CAN 新鲜反馈、现场清场、急停、已知回程姿态和唯一命令源。
3. **Calibration/analysis**：对已完成数据离线拟合；不触发真实动作。
4. **Isaac-only repair**：允许对独立、版本化 replay/override 层试验；不得改写真机路径或基础资产。

若电机未上电，先读取 manifest 的 `motor_enable_authorized`、记录的真机/CAN host 与硬件 profile：

1. 若具名单次授权明确覆盖电机使能，skill 必须主动在该真机/CAN host 执行已部署 profile 的**有界使能验证**，随后继续既有验证；不要求操作者另行手工启动。
2. OpenArm 若要求持续使能信号，则从 profile 读取已验证的 enable heartbeat 帧、频率、选定 ID 集合和失联超时；使能过程必须持续发送该**已记录**心跳，直到完整反馈 gate 成立，并在验证期间持续保持。不得把一次 `enable` 成功文本当作已使能证据。
3. 使能验证必须确认唯一 CAN writer、CAN 为 `UP` 且 RX 计数增长、每条选定总线的**全部预期电机 ID**均有稳定响应帧、新鲜且完整的关节反馈，以及操作者确认物理绿灯；再允许启动 `enable_real:=true` 路由。若 heartbeat 中断、任一 ID 消失、反馈过期或 LED 异常，立即停止真实路由和 heartbeat，记录失败，不进入位置检测。
4. 未授权、host/profile 不明确、CAN/反馈/绿灯任一失败时，禁止猜测 enable 帧、ID、类型或清故障；停止并把失败写入 preflight。此时仍可做 manifest、冻结文件哈希、只读预检、映射审计和离线分析。

每个 enable 证据必须保存 host、profile/hash、heartbeat 帧/频率的引用、CAN 状态和计数、每个预期 ID 的响应摘要、反馈时间戳、LED 确认与 trial ID。使能成功不等于运动通过；后续轨迹仍须满足单一命令源、界限、回程、receipt 与状态 freshness gate。

### CAN `DOWN/STOPPED` 自动恢复分支

在已获具名试验授权且 manifest 明确允许 `can_recovery` 时，发现 `can0` 或 `can1` 为 `DOWN`、`STOPPED`、`BUS-OFF` 或未配置 FD，不应仅报告失败后等待人工重复命令。skill 必须按以下顺序主动恢复：

1. 确认目标是记录的真机/CAN host；读取 profile 中的接口、仲裁速率、数据速率和 FD 设置。当前 OpenArm v2.0 profile 为 `can0/can1`、仲裁 `1 Mbit/s`、数据 `5 Mbit/s`、CAN-FD 开启。
2. 检查并停止该两条总线的唯一现有 CAN writer（例如 `ros2_control_node`）；不得在 writer 存活时改接口或启动第二个 writer。记录停止前 PID、节点与理由。
3. 使用项目已验证的 CAN 配置工具按 profile 配置两接口并置为 `UP`；不得用猜测的 bitrate、FD 模式、接口名或手工省略数据速率的简化命令。
4. 读取接口详细状态，要求两接口均为 `UP`、FD/速率与 profile 一致、非 `BUS-OFF`/`ERROR-PASSIVE`；随后做不含位置命令的节点发现，要求每条总线完整、稳定地返回该 profile 声明的预期电机 ID 集合。
5. 只有上述恢复 gate 通过，才可启动唯一的持续使能 heartbeat；heartbeat、完整反馈、绿灯与唯一 writer gate 仍必须通过后才允许真实路由和测量。

若配置、接口状态或任一预期 ID 检查失败，立即保持位置路由关闭，保存接口详情、配置输出、节点集合与时间戳；不得循环重试、批量 enable、清故障或发送位置目标。CAN 恢复是本次具名试验的一部分，必须记录为 `can_recovery_passed` 或 `can_recovery_failed`。


## 2. 总顺序与阻断关系

```text
Health → 同一上电静态候选 → Isaac-only replay 验收
      → 独立上电静态验证 → 映射审计 → 有效域/随机残差
      → RTF 合格 → 原始配对动态测量 → 动态候选 → 任务验证
```

- 任一 state、receipt、关节映射或安全 gate 失败：停止真实试验；证据标为 `invalid`，不得拟合或提升。
- 独立上电静态、映射审计和有效域工作可在未解决跨端 wall-time delay 时先完成。
- 动态跨端 delay、墙钟 t90、FIFO 和 drive 调参必须等 RTF 稳定 `>=0.95`；否则动态项为 `not_identified`。

### 2.1 静态—映射闭环与统一发布门

在要进入 RL 域随机化前，静态和映射工作按以下闭环执行；它们不等待动态 delay 完成：

```text
冻结候选配置与 hash
  → 离线映射审计（名称、URDF、单位约定、axis、限位）
  → Isaac live 只读审计（DOF 名称/索引、articulation 命令单位、USD DriveAPI 单位与语义）
  → 真机 profile/encoder/传动只读审计
  → 受限物理正方向/限位证据（须具名单次授权）
  → 同一上电留出 + Isaac-only replay
  → 独立上电冻结配置留出
  → 每轴证据晋升或退回映射修复
  → 统一包发布
```

每一步都写入同一 `trial_id` 或 `audit_id` 的 manifest。任一步发现名称、单位、轴向、传动或限位不一致，状态为 `mapping_mismatch`：停止该轴的参数晋升，修正**Isaac 映射/独立 override 层**后重新采集；不得修改真机控制器或用 `a/b/h` 覆盖错误。

统一包必须逐轴记录配置 hash、参数来源、同一上电留出、独立上电留出和映射审计状态。只有全部 14 轴都同时为 `mapping_audited` 与 `independent_session_validated` 时，包才可标记为 `unified_release`。未完成的轴保留冻结旧值，并在草案中标为 `not_promoted`；草案不得成为默认部署配置。

## 3. 静态位置：同一上电与独立上电

模型只用于 Isaac replay：

```text
q_emulated = a × q_nominal + b + h(direction)
```

- `a`：名义命令幅值映射候选，不自动等同机械传动比。
- `b`：不随方向改变的静态偏置候选。
- `h(direction)`：接近方向相关项，可能反映摩擦、迟滞或未建模因素；不自动等同机械背隙。
- `q_emulated`：经上述变换后发送给 Isaac 的目标；真机始终接收 canonical nominal target。

### 同一上电 session

每轴执行预注册的正向、负向和另一幅值稳态轨迹。前两次重复拟合；第三次冻结参数，为 `within_session_holdout`。通过后状态是 `within_session_candidate`，仅证明当前开机、载荷、温度和位置域内可用于 Isaac compare/replay。

### 独立上电 session

关机后重新上电，记录 calibration SHA-256、时间、温度、payload、初始姿态、profile/firmware 和控制率。**每次物理标定启动必须先执行已授权的回零/归位流程，确认所有轴达到记录的零位容差并稳定保持；随后才开始各轴测量。** 回零用于标准化初始姿态、方向历史、控制器启动状态和机械落点。冻结旧参数，禁止用新数据重拟合。再次覆盖每轴正向、负向和另一幅值，报告 raw nominal 与 frozen emulated 相对真机的 MAE、最大误差、方向差和回程误差。

“命令回到零位”与“硬件 homing/encoder 重新建零”必须在 manifest 中区分。前者只能统一姿态与方向历史；后者才能证明 encoder 参考被重建。未执行规定回零、未达到零位容差或未记录稳定窗口的 session 为 `nonstandard_startup_diagnostic`，不得用于独立上电参数晋升或全局残差结论。

通过需满足预注册任务容差、emulated 优于或不劣于 raw，且无新限位、反向、漂移或 state/receipt 缺失。无任务容差时 `0.01 rad` 仅是关节级筛查门，不能称为任务成功或长期真机精度。

## 4. 映射审计

对所有 `a≠1`、带方向项或表现异常的轴逐项记录：ROS name、真机反馈名、Isaac DOF/索引、rad/deg、正方向、axis/origin、左右镜像、传动、软硬限位、速度/力矩限制、USD drive type/target/stiffness/damping/max force、真机 controller/profile/firmware。

若发现映射错误，先修映射再重采；不得用 `a/b/h` 掩盖。全部证据一致才为 `mapping_audited`。

审计按四个证据层推进：

1. **离线资产层**：ROS 名称、URDF joint type、axis、origin 和 limit；不触发 Isaac 或真机动作。
2. **Isaac live 只读层**：articulation DOF 名称/索引、状态单位、bridge 实际 target、USD DriveAPI 属性和 unit conversion。必须明确记录：articulation position action 为 rad，而原始 USD revolute limit 与 Angular Drive target 为 deg；不能根据属性名猜测转换已经发生。
3. **真机 profile 只读层**：encoder count/angle 定义、减速/传动、零位、软件限位、控制模式、firmware/profile hash。缺失资料时状态为 `profile_evidence_missing`，不推断传动比。
4. **物理几何层**：每轴安全小幅正/负动作和接近限位的非接触证据，确认实际正方向和有效限位；必须先通过 Health/enable/唯一 writer gate，并取得该具名试验授权。

`a` 只在四层未发现映射错误后才可保留为经验幅值映射；它仍不是自动确认的机械传动比。审计结果只可为 `mapping_audited`、`mapping_mismatch` 或 `profile_evidence_missing`，不得以“未检查”替代通过。

## 5. 有效域与随机残差

从中心安全位置、空载、慢速、单方向开始，每次只扩展一个条件维度：位置区间、方向、速度、payload、温度、控制频率。每个条件组合至少三次，保存状态、receipt 和全部条件标签。

```text
residual = measured_feedback - model_prediction
```

- 分箱内残差均值跨重复稳定且随条件变化：系统性条件项；新模型必须重新做留出和独立上电验证。
- 分箱内均值接近零但 std/p95 宽：随机残差；保存样本数、均值、std、p05/p95，供 Isaac 训练随机化。
- 无数据的新条件：`out_of_domain`；不得静默外推固定补偿。

随机化永远不改变真机命令。

## 6. RTF 与动态问题

`physics_realtime_factor = physics advanced seconds / wall seconds`。RTF 低说明物理时间推进比墙钟慢；它不影响静态稳态位置的拟合资格，但使跨端墙钟 delay、t90 和控制频率比较失真。

动态测量前需同时满足：Isaac timeline/physics 正推进；state/bridge/receipt 可见；关闭仅供人查看的 viewport 后在保留实际策略相机条件下 RTF 稳定 `>=0.95`；原始真机—Isaac 对比关闭静态 replay，使两端接收同一 nominal target；有单独的动态真实试验授权。

RTF 未达标时允许做 Isaac-only physics-time baseline 和运行性能诊断，但必须保持 `delay=not_identified`：不加 FIFO、不用墙钟 t90 改 drive、不把渲染或主循环瓶颈拟合成真机延迟。

对 RL，delay 不是当前静态标定的阻断项，但也不能视为无影响：慢速稳态到位任务可先用静态 replay 与频率记录训练；快速接触、视觉闭环或高带宽跟踪中，action/observation delay 会改变闭环状态，必须在 RTF 合格后测量，或以保守的、记录来源的范围做随机化。未测得的 delay 不能凭直觉设为零，也不能写为固定补偿。

## 7. 动态测量、归因与修复

每个 waypoint 记录 command published、accepted receipt、target applied、first physics response、state published 和两端反馈。两端各自用其稳定起点/终点归一化：

```text
q0 = 命令前稳定窗口中位数
q∞ = 命令后稳定窗口中位数
r(t) = (q(t)-q0)/(q∞-q0)
```

计算 onset、t10/t50/t90/t95、settling、峰值速度、超调和方向差，以 **physics-time** 作动态候选判据。

| 曲线证据 | 候选解释 | 后续动作 |
|---|---|---|
| 整体平移、形状相近 | command/observation delay | 只在共同时间基准下估计延迟 |
| onset 相近、rise/t90/peak 不同 | 带宽、drive、速度/加速度限制、控制率 | 一次扫描一个参数族 |
| 正负方向差异 | 摩擦、迟滞、背隙动态 | 分方向低幅 ramp 与留出验证 |
| 同条件方差大、均值稳定 | jitter/随机残差 | 建立随机化分布 |

所有 drive/physics 候选先在 Isaac-only、可回滚的版本化 override 上验证；一次只改一个参数族。通过同一上电第三次留出、另一幅值/ramp 和独立上电后才可标为 `dynamic_candidate`。不得修改基础 USD/URDF/真机 controller。

## 8. 证据状态、版本与回退

状态固定为：`measured`、`within_session_candidate`、`independent_session_validated`、`mapping_audited`、`dynamic_candidate`、`task_validated`、`not_identified`、`out_of_domain`、`invalid`。

每次变更均保存：manifest、原始数据、配置和场景 hash、代码版本、参数 diff、统计、判定、回退版本。规则调整须记录“规则版本 → 证据 → 决策 → 配置版本 → 验证结果”；新规则不能追溯改变旧数据的通过状态。

## 9. RL 前的最小标定出口

完成静态全轴包后，不要求为每轴拟合唯一动态 drive。按以下顺序完成剩余工作：

1. **动态全轴范围测量**：在 RTF 合格条件下记录 action/observation rate、端到端 delay、jitter、速度、超调和 payload 变化范围；稳定确定项才可建模，其余作为随机化范围。
2. **本体 TF 与 TCP**：验证 `world → body → base → ee → TCP` 的固定变换、左右 base 关系和多姿态 FK；这独立于相机标定。
3. **末端与接触层**：验证夹爪开度/力、物体质量与质心、接触摩擦/恢复、桌面与碰撞几何。`JointState.effort` 为空时不得把它当作接触力证据。
4. **任务级闭环**：在保留训练随机化范围的条件下，报告任务成功率、终端误差、安全停止和跨 session 重复性。

相机内外参与视觉随机化可作为独立的感知层加入；它们不替代上述本体、接触或任务级证据。
