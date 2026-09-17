# OpenArm Sim2Real 标定与验证工具包 v5

这是当前 skill 实际使用的程序、规则文档、标定配置和关键结果的可移植快照。

包含：

- `alignment/*.py`：健康检查、命名映射、静态/动态测量、Isaac replay、验证和分析程序。
- `alignment/*.sh`：真机/Isaac 启动、部署、恢复和有界试验 runner。
- `alignment/*.md`：中文流程、动态 gap、运行性能、夹爪标定和集成台账。
- `alignment/*.json/*.yaml/*.csv`：映射、关节限位、试验 manifest 和配置。
- `alignment/calibrations/`：v3 基线和 R J5 v4 候选。
- `alignment/calibration_packages/`：静态 14 轴和夹爪候选汇总包。
- 关键结果：14 轴独立上电静态汇总、最近零位门和夹爪无效试验证据。

当前状态是 `static_validated_gripper_incomplete`。夹爪读数尚未形成有效拟合；TF/TCP、动态参数和相机标定不在本版本的完成范围内。所有真实动作仍受 skill 的具名授权、归零、反馈新鲜度、唯一 writer、CAN 和急停门控约束。

归档日期：2026-09-17。
