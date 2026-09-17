# OpenArm Isaac replay v4：右 J5 独立上电证据包

这是右 J5 的部分标定包，不是 14 轴统一发布包。真机始终使用 canonical nominal target；仅 Isaac replay 使用本包中的 `calibration.json`。

冻结 v4 在 `openarm_right_j5_v4_independent_power_holdout_v2` 的 18 个稳态 waypoint 上通过：raw nominal→real MAE 为 0.011187 rad，Isaac emulated→real MAE 为 0.001718 rad，最大配对误差为 0.002156 rad。

`package_manifest.json` 和文件 SHA-256 用于复现与审计。不得据此修改真机 CAN、控制器、USD 或 URDF。
