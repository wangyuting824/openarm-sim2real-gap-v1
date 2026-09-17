# OpenArm 14 轴统一标定包草案 v1

这是统一发布包的索引和冻结候选副本，不是可部署的正式 14 轴标定包。

- 14 轴均保留 v3 静态 Isaac-only compare/replay 证据。
- 右 J5 使用 v4 候选，并已通过独立上电留出验证：raw MAE 0.011187 rad，emulated Isaac-vs-real MAE 0.001718 rad。
- 其余 13 轴仍保留冻结 v3 参数，等待各自的映射审计和独立上电验证；不能把它们标为已完成跨上电验证。
- `calibration_candidate.json` 是 v4 的逐字副本；不得直接修改。后续正式发布将新建版本，并把每轴证据、配置哈希和验收结果写入 manifest。

映射审计的目标是证明每个 `a != 1` 是实际静态映射差异，而不是关节名、单位、轴向、传动比、限位或 USD drive 语义错误。
