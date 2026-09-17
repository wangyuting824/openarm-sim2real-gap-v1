# OpenArm Sim2Real Skill 逻辑审查

本文审查当前 `openarm-sim2real-gap` skill 的边界和下一轮应补齐的逻辑。它不否定现有 14 轴 replay 标定；现有结果只适用于已测关节位置控制的 **Isaac compare/replay**。

## 已成立的逻辑

1. 先完成 Isaac sim-only tracking，再采集真实 gap。
2. 真机每次动作需要独立命名授权、边界、回程和现场安全确认。
3. endpoint 数据先分类为 offset、比例、方向迟滞、随机残差或 delay，再决定补偿层。
4. 补偿默认仅进入 Isaac replay；不自动改真机、USD、URDF 或 drive。
5. 缺数据、receipt 缺失、跨轴 stale stream 的样本不自动提升为标定项。

## 需要修正或补全的逻辑

| 优先级 | 当前不足 | 风险 | 应补齐的规则 |
|---|---|---|---|
| P0 | 将同一 session 的第三次重复称为 held-out 验证 | 不能证明跨时间、温度、上电状态和负载仍有效 | 区分 `within_session_holdout` 与 `independent_session_validation`；只有后者可提升为长期默认标定。 |
| P0 | `q_real=a*q_sim+b+h(direction)` 仅使用前一名义目标决定方向 | 真实迟滞还与真实接近方向、速度、停留时间、负载和零交叉有关 | 记录前一真实反馈、速度、方向翻转和 hold 时长；超出标定域时回退为未补偿或随机化。 |
| P0 | settled endpoint 无法估计 delay，却容易被误解释为动态一致 | 控制频率、DDS、传感器和 Isaac step 的时间差未被补偿 | delay 必须独立使用 timestamped ramp/step 估计 response onset、t90/t95 与 observation delay；没有该实验则保持 `not_identified`。 |
| P0 | J6 的 `a` 为比例/传动候选但仍直接启用 replay | 轴方向、单位、传动比或 limit 映射错误会被拟合掩盖 | 每个 scale 项必须附带 mapping audit：URDF/Isaac DOF 名称、单位、符号、传动比、限位和电机 profile 版本。 |
| P1 | replay 只校验 Isaac 是否到达“等效目标” | 可证明 bridge 工作，但不能证明真实任务结果更接近 | 验收应增加同一命令下 real-vs-emulated 的独立真实轨迹指标；任务层还应加入末端位姿、接触和成功率。 |
| P1 | 标定文件缺少有效域 | 在未采样的关节角度、速度或负载上外推 | 写入每轴 position/velocity/payload/temperature/控制周期有效范围；越界时拒绝补偿或采用保守随机化。 |
| P1 | 跨主机同步只复制文件，未验证版本一致 | Isaac 可能运行旧 bridge 或旧 JSON | deploy 后要求远端 SHA-256、bridge console 的 config 路径和 daemon status 三者一致，再开始 replay。 |
| P1 | 单看 ROS publisher count 不能充分保证唯一命令源 | endpoint 存在不等于正在发布，外部 CAN 写入也不在 ROS 图中 | 真实试验使用单一 runner 锁、记录 PID/节点/GID，并在开始前后保存 controller topic 与 CAN ownership 证据。 |
| P1 | ISAAC 的 drive 修复只验证位置 tracking | 接触、摩擦、惯性、重力和控制器增益仍可能不真实 | 把 drive 参数、solver dt、substeps、重力、摩擦、质量/惯量和关节限位写入场景指纹；任务含接触时另做接触标定。 |
| P2 | 关节层标定不覆盖感知与坐标系 | 相机、桌面、外参、抓取物体和末端工具仍可能是主要 gap | 增加相机内外参、base/world/object frame、桌面高度、工具 TCP、光照/材质和观测 delay 的独立流程。 |
| P2 | 随机噪声只被分类，未转成训练策略 | 固定 offset 在噪声主导时会过拟合 | 保存均值、方差、分位数和相关条件；把随机项转成 Isaac domain randomization 与策略鲁棒性评估。 |

## 对当前 v3 的解释

- v3 是 **joint-position compare/replay calibration**，不是机械臂几何、相机或接触的完整标定。
- 它使 Isaac replay 复现已测真机的关节响应；它不表示应把 offset 反写入真实控制器。
- 右 J7 已有独立真实复验和同 session 留出改善证据，因此可进入 Isaac-only replay；下一步仍需独立 session 的真实复验来证明长期稳定性。
- delay、随机项、工具/相机/接触 gap 仍未完成，配置中不得伪造这些参数。

## 下一轮最小改进顺序

1. 部署 v3，完成 14 轴 Isaac-only replay 与远端文件 hash 记录。
2. 选 J6/J7 各做一次独立 session 的相同轨迹，验证漂移和方向项。
3. 增加低幅 ramp，测每轴 command-to-feedback delay。
4. 对含 payload、不同速度和不同关节区间做分层采样，得到有效域与随机残差。
5. 在真实任务上比较 nominal、replay emulation、随机化策略与残差策略的末端误差和成功率。

### 第 3、4 步的具体含义

- **低幅 ramp**：从安全起点向目标连续、匀速地缓慢移动，而不是一步跳到目标。例如总位移 `0.025 rad`、持续 `0.5–1.0 s`，再保持到稳定。它和阶跃使用同一 receipt 与反馈记录，目的是检查延迟和速度限制在较温和输入下是否仍存在；它不是提高速度或扩大真机动作范围。真实采集仍需单独命名授权和现场安全确认。
- **有效域**：一条参数可以被使用的条件范围。例如“右 J7、位置区间 A、空载、20–25°C、50 Hz 控制、速度不超过某阈值”。只要位置、速度、payload、温度或控制周期超出已采样范围，就不能把当前 `a/b/h` 或动态参数当作已验证事实。
- **随机残差**：先用静态模型预测稳态位置，再计算 `残差 = 实测值 − 模型预测值`。同一条件下残差均值持续偏离零，说明还有可辨识的系统性项；均值接近零但重复实验的标准差、p95 或方向相关性较大，才属于随机残差。它应保存为按关节、方向、位置、速度、payload 分箱的分布，在训练中随机采样，而不是写成一个固定 offset。
- **如何采集和区分**：在每个位置区间、方向、速度和 payload 组合下至少重复三次；前两次拟合均值模型，第三次留出检查。再换一组位置或速度复验。只有误差随条件稳定变化，才扩展模型；误差只在重复间无规律波动，才进入随机化范围。跨上电 session 的重复用于判断该分布是否长期有效。

## 动态 gap 的实施规则

动态补齐采用独立协议，见 [dynamic_gap_protocol_zh.md](dynamic_gap_protocol_zh.md)。原始动态采集要先关闭静态 replay，使两端接收相同 canonical target；对两端各自以实测稳态位移归一化后再比较 onset、t10/t50/t90/t95、峰值速度、超调和稳定时间。这样静态 `a/b/h(direction)` 不会被误判为 delay。

补偿按证据放入 Isaac 的 command FIFO、observation FIFO、控制频率/零阶保持、速度加速度限制或有界随机化层。拟合前两次、同 session 第三次留出、另一幅值或 ramp 验证、独立上电 session 验证，依次决定候选、Isaac replay 可用和长期默认。所有动态项均记录位置/速度/负载/温度/控制周期有效域；未识别项保持 `not_identified`。
