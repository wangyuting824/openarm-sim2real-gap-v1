# OpenArm 静态标定的论文术语与证据边界

## 变量定义

对某一关节、同一稳态 waypoint，定义：

- `q_nominal`：canonical nominal target；真机接收的原始关节目标（rad）。
- `q_replay`：replay-compensated simulator target；由冻结的 Isaac replay 映射生成、发送给 Isaac 的目标（rad）。
- `q_real`：真机稳态反馈位置（rad）。
- `q_sim`：Isaac 稳态反馈位置（rad）。

冻结 replay 映射为：

```text
q_replay = a q_nominal + b + h(direction)
```

推荐报告三种误差：

```text
e_nominal = q_real - q_nominal
e_replay  = q_sim - q_real
e_track   = q_sim - q_replay
```

报告 MAE、最大绝对误差、均值/有符号偏差、样本数、方向、幅值、上电 session 和配置 SHA-256。

## 不建议的术语

- 不把 `raw` 单独作为论文变量；它没有说明是 raw command、raw encoder reading，还是未经补偿的误差。正文可写“nominal-target baseline”，表格使用 `e_nominal`。
- 不把 `emulated` 单独作为最终误差名称。若保留实现变量名，首次出现必须定义为“replay-compensated simulator target (`q_replay`; implementation name: `q_emulated`)”。
- `a` 只能称为经验幅值映射系数；没有 encoder/传动证据前，不能称为已识别的减速比。
- `h(direction)` 只能称为方向相关经验项；不能直接称为机械背隙。

## 本次独立上电 v3 remaining13 的可报告性

- L J1–L J5、L J7：轨迹、receipt、模拟跟踪与当前 `0.01 rad` 筛查门通过；可称为“通过本次独立上电静态留出筛查”，但统一包前仍需 `mapping_audited`。
- L J6：全部 18 个 waypoint 和 receipt 完整，但负向 `-0.05 rad` 三次重复的 `e_replay` 分别为 `-0.013777`、`-0.013395`、`-0.013014 rad`。`e_track` 约 `+0.000021 rad`，说明问题不在 Isaac tracking，而在冻结 replay 对该独立上电负向真实响应的残差；因此不得晋升。
- R J1：只记录到一个不完整 waypoint，随后因 `no accepted router receipt` 中止；不能报告为模型误差或失败率样本。
- R J2、R J3、R J4、R J6、R J7：尚未测量。

## 论文级结论边界

可以报告“冻结 replay 映射在完成的轴/条件中降低了 nominal-to-real 静态误差”，但不能报告“全 14 轴独立上电验证通过”，也不能报告长期泛化、动力学一致性或接触任务成功。所有数值应链接到原始轨迹、manifest 和配置 hash。
