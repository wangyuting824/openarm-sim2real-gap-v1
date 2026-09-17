# OpenArm 动态 Gap 校正运行手册

本文将动态校正限定为可审计的五个阶段。它适用于 OpenArm 本体关节，不修改基础 USD，不自动向真机发命令。

## 阶段 A：运行时门控

先以与后续采集相同的场景、RL 相机、分辨率和策略频率运行 10 秒实时倍率探针。可关闭人工 GUI viewport，但不得关闭策略使用的 Replicator RenderProduct。

```bash
ros2 service call /openarm/isaac_gap/measure_realtime_factor std_srvs/srv/Trigger '{}'
```

通过条件是 `physics_realtime_factor >= 0.95`。低于该值时，停止本轮动态参数校正，只处理 headless/viewport、RenderProduct、未使用的 annotator、场景负载及 CPU/GPU 资源。当前已知的 `0.2725`（GUI）和 `0.6628`（仅关闭 viewport）均不通过此门。

当前仓库未保留旧 URDF 导入路径的 USD；先通过 daemon 从已打开的 Isaac stage 导出可复用快照。快速 headless A/B 使用该快照，保留其中已定义的 Replicator RenderProduct，并拒绝与现有 Isaac/Kit 进程同时运行：

```bash
cd ~/openarm_ws
ros2 service call /openarm/isaac_gap/export_current_stage std_srvs/srv/Trigger '{}'
# 等 daemon event 显示 loaded=export_current_stage 后，关闭 GUI Isaac 实例。
ssh tangyuan@192.168.18.72 \
  'cd /home/tangyuan/openarm_ws && bash alignment/run_isaacsim_headless_realtime_probe.sh'
```

它在结果文件和标准输出写入 `OPENARM_HEADLESS_RTF=<json>`。仅当该值达到门槛后，才关闭 headless 实例、恢复原运行环境，并进入阶段 B。

保存本轮 RTF JSON、USD root layer、动态 bridge、state publisher、场景和运行时配置的哈希。不得使用 UI timeline 值代替 PhysX callback 累积时间。

## 阶段 B：原始配对采集

静态 v3 replay 必须关闭。真机与 Isaac 接收完全相同的 canonical target；记录器需同时保存 command、accepted receipt、real state、Isaac state 和 Isaac timing。

首个真机试验应只限单轴，使用已经审查过的 J7 范围：测得起点附近 `+0.025/-0.025/+0.050/-0.050 rad`，每项重复 3 次，target/return 各保持 2 s，50 Hz 持续发布，单步不超过 `0.05 rad`、总偏移不超过 `0.15 rad`。这一步需要新的、单次有效的物理授权；授权必须明确试验 ID、关节、轨迹、最大偏移、回程、急停、工作区、断电位置、单一 publisher 和实时反馈确认。

## 阶段 C：离线分析与候选门控

```bash
python3 alignment/analyze_dynamic_gap.py \
  --input <trial>/raw.json \
  --output <trial>/dynamic_metrics.json

python3 alignment/validate_dynamic_correction_gate.py \
  --realtime-probe <same-runtime>/isaacsim_realtime_factor_probe.json \
  --analysis <trial>/dynamic_metrics.json
```

分析器分别保存 wall-time 和 physics-time：

- wall-time 用于端到端部署风险；
- physics-time 用于识别 Isaac 模型自身的 onset、t10/t50/t90/t95、超调、settling 与 return；
- 真机—Isaac 动态候选只读取 physics-time 汇总。

门控失败时不改 drive、不加 FIFO、不保存 override。必须先解决失败原因。

## 阶段 D：Isaac-only 候选扫描

通过阶段 C 后，按以下顺序且每次只改一类参数：

1. drive stiffness、damping、max force；
2. 控制或 command update rate；
3. velocity、acceleration、jerk 限制；
4. physics dt、substeps、solver iteration。

每个候选均为可回滚的 live session 修改。每项重跑同一物理时间曲线，并保存 RTF、t90、超调、稳态误差、return 曲线和配置指纹。若 Isaac 的 onset 与真机接近但 physics-time t90/超调不匹配，才扫描 drive/限速/控制率；若两侧曲线形状接近且整体时间平移，才考虑受限 command/observation buffer。

## 阶段 E：验证与提升

候选必须依次通过：

1. 第三次重复的 within-session holdout；
2. 未参与拟合的幅值或 ramp；
3. 不同上电/温度/负载条件下的独立 session；
4. 静态 v3 replay 与动态层联合作用下的 Isaac-only 全轴回归。

通过后才创建独立的 override/calibration layer。该层须记录候选 ID、参数、有效位置/速度/负载域、RTF、曲线、场景/配置哈希和证据哈希。基础 USD 与真机命令路径保持不变。
