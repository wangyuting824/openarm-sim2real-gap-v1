# OpenArm 统一标定汇总包 v5（静态 14 轴 + 夹爪候选）

本包是当前证据的单一索引，不把未完成项目伪装成已通过标定。Isaac replay 只作用于 Isaac 侧，不修改真机控制器、CAN、基础 USD 或 URDF。

## 已有有效证据

- v3：14 个转动关节均有 Isaac-only replay/compare 证据。
- v4：独立上电且先归零的 14 轴静态留出试验已完成；12 轴通过 `0.01 rad` screening，L J6 与 R J5 标为 `accepted_with_residual_randomization`，不阻断 RL 使用，但残差必须保留在随机化范围。
- R J5：v4 独立上电留出验证已保留，参数位于 `openarm_isaac_replay_calibration_v4_candidate_right_j5.json`。
- 零位：最近一次夹爪试验前的 14 轴零位门通过，3 秒内最大偏差为 R J7 `0.02422 rad`。

## 尚未完成

- 夹爪开口扫描没有有效读数：router 安全门阻断后自动返回，`left.json` 的 readings 为 0；`12 mm` 和 `17 mm` 只是操作记录，不能进入拟合。
- 夹爪仍需重新执行逐点命令、反馈和卡尺宽度采集。
- TF/TCP 尚未固定安装参考，也没有物理多姿态验收。
- 映射审计仍缺 Isaac live drive 单位、真机 encoder/传动 profile、物理正方向与限位证据。
- 动态 delay、带宽和 t90 仍未形成可写配置参数；RTF 低于 0.95 时墙钟动态指标仅作性能诊断。

## 规范

所有物理试验先归零并通过实际反馈门；同一上电留出只支持 within-session 结论，独立上电才可用于跨 session 晋升。夹爪每侧是一个连续 position 执行器，Isaac 的第二 finger 是 mimic，从未测得的开口宽度不能推断夹持力。

## 文件索引与 SHA-256

详见同目录 `package_manifest.json`。原始配置和结果保持在 `alignment/calibrations/` 与 `alignment/results/`，本包不复制并覆盖原始证据。
