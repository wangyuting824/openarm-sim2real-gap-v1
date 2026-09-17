# Isaac Sim 动态响应慢：运行时诊断结论

日期：2026-09-16。范围：Isaac-only、J7 动态试验期间的实时运行能力；不向真实机器人发送命令，不修改基础 USD。

## 结论

现阶段首要问题是 **GUI viewport/RTX 渲染负载使 PhysX 低于实时运行**，不是已有数据能够支持的 USD 关节 drive 或 PhysX dt 配置错误。

关闭 active viewport 更新的可逆 A/B 中，物理实时倍率从 `0.2725` 提升到 `0.6628`，约为 `2.43x`。这说明至少大部分墙钟慢响应来自渲染与主循环负载。viewport 已恢复。

仍未达到实时（RTF < 1），所以不能说所有性能问题已解决；剩余负载最需要检查的是 Replicator RenderProduct、RTX 相机/传感器、场景复杂度，以及主机 CPU/GPU 饱和情况。

## 证据

| 条件 | 物理实时倍率 | PhysX step Hz | Kit update Hz | 解释 |
| --- | ---: | ---: | ---: | --- |
| 正常 GUI | 0.2725 | 16.35 | 24.42 | 10.03 s 墙钟仅推进 2.733 s 物理时间 |
| `minFrameRate=15` | 0.2697 | 16.18 | 24.17 | 无实质改善 |
| `minFrameRate=10` | 0.3151 | 18.91 | 22.59 | 仅有限改善，且 update 更慢 |
| 关闭 active viewport 更新 | 0.6628 | 39.77 | 59.35 | GUI/渲染为主要瓶颈 |

每个 PhysX 步长均为约 `16.667 ms`（60 Hz 物理 dt）。问题是墙钟时间内没有足够多的物理步被执行，不是 dt 被改大。

## 对 Sim2Real 的影响

RTF 低于 1 会直接放大以墙钟测量的 command-to-state 延迟和 `t90`，从而把主机渲染性能误判成机器人/drive 很软。它还会使按固定墙钟频率发送的控制命令与仿真物理推进不同步。因此在 RTF 未稳定接近 1 时：

- 动态拟合必须同时报告 physics-time 和 wall-time 指标；
- 不应用墙钟 `t90` 去调 stiff/damping 或保存 USD override；
- 视觉闭环和真实时间控制的 Sim2Real 结果不具可比性。

纯离线轨迹或按 physics-time 重采样的模型仍可用于检查物理形状，但不能证明实时闭环表现。

## 下一步

1. 在 viewport 已恢复的条件下，单独关闭 Replicator RenderProduct/RTX 传感器并复测 RTF。
2. 以同一 USD 运行 headless/no-window 基准；若 RTF 接近 1，确认是渲染管线问题。
3. 若 headless 仍明显低于 1，采集 CPU/GPU 利用率和 Isaac profiler/Tracy 结果，检查场景物理复杂度与主机资源。
4. 仅当 RTF 稳定接近 1 后，重新采 J7 与全轴的 physics-time `t90`、超调和稳态误差，再决定是否调 drive 并保存独立 override layer。

## RL 视觉观测的运行方式

RL 需要的 Replicator/相机 RenderProduct 不能关闭；关闭的是仅供人工查看的 active GUI viewport。两者独立：无窗口或关闭 viewport 更新时，ROS、PhysX 和 Replicator 仍可产生策略图像。

视觉 RL 的推荐配置是：以 headless/no-window 运行，保留策略实际使用的相机和 annotator；按真实相机分辨率与策略频率渲染，移除未使用的 RGB、深度、语义分割或额外相机。物理可维持 60 Hz，而图像只在策略需要新观测时更新，例如真实系统为 15 Hz，就以 15 Hz 更新图像并在中间物理步保持最近观测。该频率必须与真实传感器和部署策略一致，不能仅为提高基准分数而随意降低。
