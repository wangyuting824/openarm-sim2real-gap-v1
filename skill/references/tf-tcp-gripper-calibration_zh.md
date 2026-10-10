# OpenArm TF、TCP 与夹爪执行器标定

本模块覆盖机器人本体几何和末端执行器；不覆盖相机内外参、物体识别或抓取策略。

## 1. 要固定的坐标链

```text
world → openarm_body_link0 → left/right_base_link → … → ee_base_link → TCP
```

- `world → openarm_body_link0`：工作台或治具坐标到本体根节点的固定变换。
- `openarm_body_link0 → left/right_base_link`：双臂 base 的固定几何关系。
- `ee_base_link → TCP`：工具中心点的固定位置和朝向。

每个变换必须记录父 frame、子 frame、平移（m）、四元数、变换来源、测量时间、资产/URDF hash 和适用的末端工具。不得用相机 TF、关节 replay 参数或任务成功率代替本体 TF 证据。

## 2. TF/TCP 闭环

1. **离线资产审计**：读取 URDF/USD 的 joint origin、axis、base 与末端链，导出模型 FK。此步骤只证明模型内部自洽。
2. **固定基座测量**：用工装、量具或外部测量参考确定 `world → body` 与左右 base 关系；固定安装一旦改变，旧结果立即失效。
3. **TCP 测量**：以实际工具尖端/夹爪中心定义 TCP；换工具、夹爪垫或安装方向即建立新的 TCP profile。
4. **多姿态验证**：每臂至少在多个安全、小幅姿态比较真实 TCP 与 FK TCP 的位置和姿态。整体恒定偏移优先检查 base/TCP；随关节变化的误差返回 joint axis/origin/zero 审计。
5. **发布**：仅当坐标、单位、frame 名称、工具 profile 和多姿态误差均满足任务容差时，写入版本化 TF/TCP override。基础 URDF/USD 不直接改写。

报告位置误差（m）、姿态误差（rad/deg）、姿态数、最大/MAE、任务容差和工具 profile。若任务容差未定义，不得声称 TCP 已通过。

## 3. 夹爪执行器闭环

夹爪状态至少区分：`command`、真机 `feedback`、Isaac `feedback`、实际开口宽度（m）和接触后有效开口。没有力传感器或可靠 effort 时，不得把 `JointState.effort` 当作夹持力。

1. **开口映射**：空载、无接触下测 command → 真机开口宽度/反馈；分别覆盖开、闭、回程和中间开度。
2. **限位与速度**：记录最小/最大安全开度、到位时间、速度和回程差；命令永不超过实测安全限位。
3. **Isaac 对齐**：确认 finger DOF、单位、左右手指耦合、碰撞几何和开口定义一致；Isaac-only 先验证 command → 模拟开口。
4. **负载/接触**：对代表性物体记录闭合后的稳定开度、滑移/保持和失败模式。它是接触层证据，不应用固定空载偏置掩盖。
5. **RL 参数化**：稳定 command-to-open-width 关系可作为 Isaac 映射；速度、回程、接触后压缩、摩擦和物体尺寸差写成随机化范围。

## 4. 状态与阻断

- `tf_tcp_candidate`：资产和初始测量完成，尚无多姿态验收。
- `tf_tcp_validated`：固定工具与 base 下，多姿态误差满足任务容差。
- `gripper_kinematic_validated`：空载开口、限位、速度及 Isaac DOF 映射通过。
- `gripper_contact_characterized`：代表性负载/物体的保持与滑移范围已记录。
- 任一 frame、单位、工具 profile、关节映射或 safety gate 不明：停止真实动作，保留只读/离线工作。

真实动作仍需具名单次授权、回零/已知起点、现场清场、急停、绿灯和唯一 CAN writer。TF/TCP 或夹爪补偿只可写入独立版本化 override；不得修改真机控制器、CAN、基础 USD 或 URDF。

## 5. OpenArm 夹爪空载开口扫描的执行规则

使用 `alignment/manifests/openarm_gripper_kinematic_scan_v1.yaml` 和
`alignment/run_openarm_gripper_kinematic_scan_v1.sh` 进行首次开口标定。

- 它只允许逐侧发送 `openarm_left/right_finger_joint1` 的连续 position target；不允许发送任何 arm joint target。
- 扫描在 URDF 限位内保留边距，子步不得超过 `0.015 rad`，每个点至少保持 3 秒；每侧完成后必须回到开始时的测得关节位置。
- 开始前必须同时通过：真实 14 个 arm joint 在 `±0.03 rad` 零位内、真实和 Isaac 状态新鲜、唯一命令发布者、CAN/绿灯/急停/清场门通过，且手指间无物体。
- 每个稳定点都记录 command、真机 feedback、Isaac feedback、receipt、方向和人工卡尺的最小垫间距（mm）。卡尺读数缺失则试验可保留为轨迹诊断，但不得拟合或发布开口标定包。
- 分别对正向与反向数据拟合候选 `q_rad → opening_mm`；中间点保留为留出验证。未声明任务开口容差时，结果状态只能为 `gripper_kinematic_candidate`。
- `finger_joint2` 仅是 Isaac 的 mimic 从属 DOF；真机每侧只有一个受控夹爪执行器。不得将 Isaac 的两个 finger DOF 误写为两个真机夹爪电机。
