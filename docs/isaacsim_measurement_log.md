# Isaac Sim 测量台账：视觉、双臂协同与控制

本文件是本轮 Isaac Sim 测量的唯一持续更新台账，可直接粘贴到飞书文档。只记录视觉、双臂协同和控制的有效测量结果；故障、无效试次、排查过程与修复方案统一记录在原 `README.md`。物体、工作区与接触不在本轮范围内。历史 MuJoCo 记录仅保留在 `README.md` 中作审计，不作为本表的测量来源。

## 记录规则

- `measured`：有本轮 Isaac Sim 输出文件和可解释的数值。
- `partial`：有部分证据，但不足以验收完整参数。
- `not_configured`：场景或测试条件尚未定义。
- `not_measured`：应测但尚未产生有效记录。
- 所有时间均为当前仿真/ROS 主机时间；没有真机数据时不外推为真机性能。

## 待执行测试

| 顺序 | 测试 | 运行位置 | 脚本与输出 | 写入本表的参数 |
|---|---|---|---|---|
| 1 | physics/control tick | Isaac Sim Script Editor | `isaacsim_measure_physics_tick.py`；10 s 后生成 `control/tick_metrics.json` | `physics_step.mean_hz`、`kit_update.mean_hz`、时间间隔统计。 |
| 2 | 独立左右 J1 receipt skew | 宿主机终端和 ROS Docker 容器 | 按 `isaacsim_test_scripts.md` 第 4.2 节运行；生成 `control/independent_action_skew.json` | left/right command→receipt、`independent_receipt_skew_s`。 |
| 3 | 顶视任务相机 | Isaac Sim Script Editor | 已完成：`isaac_task_camera_20260915_112255/vision/`，含 `camera_info.json`、`frame_timestamps.csv`、10 张 PNG。 | 已写入视觉参数；渲染条件仍缺独立标定。 |
| 4 | 交接窗口 | Isaac Sim Script Editor | 配置任务交接目标后运行 `isaacsim_capture_handoff_window.py`；生成 `bimanual/handoff_metrics.json`。 | 交接目标位姿、位置/姿态容差、连续交接窗口；需先定义任务目标。 |

## 视觉

| 参数 | 当前值/状态 | 状态 | 证据 | 解释与限制 |
|---|---|---|---|---|
| 任务相机 | 顶视 `ceiling`：`/World/openarm_task_camera`；位置 `[0.0, 0.0, 1.2] m`，朝向 `[0.0, 0.0, 0.25] m` | `measured` | `isaac_task_camera_20260915_112255/vision/camera_info.json` | 本轮创建的任务相机；外参为 Isaac Sim 世界坐标。 |
| 已枚举 Camera prim | 4 个：`/OmniverseKit_Persp`、`/OmniverseKit_Front`、`/OmniverseKit_Top`、`/OmniverseKit_Right` | `partial` | 同上 | 均为编辑器视口，不能作为任务图像或标定证据。 |
| `/OmniverseKit_Persp` 位姿与内参 | 位置 `[0.9661324735, 0.9661324735, 0.9661325698] m`；焦距 `18.1475620 mm`；水平/垂直光圈 `20.9549999 / 15.2908001 mm` | `measured` | 同上 | 编辑器透视视口，不是任务相机。 |
| `/OmniverseKit_Front` 位姿与内参 | 位置 `[5.0, 0.0, 0.0] m`；焦距 `50.0 mm`；水平/垂直光圈 `50.0 / 50.0 mm` | `measured` | 同上 | 编辑器前视视口，不是任务相机。 |
| `/OmniverseKit_Top` 位姿与内参 | 位置 `[0.0, 0.0, 5.0] m`；焦距 `50.0 mm`；水平/垂直光圈 `50.0 / 50.0 mm` | `measured` | 同上 | 编辑器顶视视口，不是任务相机。 |
| `/OmniverseKit_Right` 位姿与内参 | 位置 `[0.0, -5.0, 0.0] m`；焦距 `50.0 mm`；水平/垂直光圈 `50.0 / 50.0 mm` | `measured` | 同上 | 编辑器右视视口，不是任务相机。 |
| 分辨率、FPS、图像帧 | `640×480`；请求 `1.0 Hz`；PNG `10` 帧 | `measured` | `isaac_task_camera_20260915_112255/vision/camera_capture_metrics.json`、`vision/frames/*.png` | 10 s 采集；实际帧间隔以时间戳 CSV 为准。 |
| CameraInfo、内参、外参、畸变 | `K=[732.9992842,0,320, 0,753.3843437,240, 0,0,1]`；`plumb_bob`，`D=[0,0,0,0,0]`；外参见任务相机位姿 | `measured` | `isaac_task_camera_20260915_112255/vision/camera_info.json` | 内参由 `24.0 mm` 焦距、`20.955/15.291 mm` 光圈及图像尺寸导出；未注入畸变。 |
| 曝光、光照、背景、遮挡、噪声 | 曝光使用默认相机设置；光照和背景使用已加载 USD 场景；遮挡未标注；未注入传感器噪声 | `partial` | `isaac_task_camera_20260915_112255/vision/render_conditions.json` | 有本次渲染条件记录，但没有独立曝光标定、遮挡量化或噪声模型。 |
| 帧时间戳 | `10` 条（另含 CSV 表头，共 `11` 行） | `measured` | `isaac_task_camera_20260915_112255/vision/frame_timestamps.csv` | 每帧记录 `sim_time_s`、`wall_time_s` 和对应 PNG 文件。 |

## 双臂协同

| 参数 | 当前值/状态 | 状态 | 证据 | 解释与限制 |
|---|---|---|---|---|
| 左右臂名义角色 | left=`giver`；right=`receiver` | `measured` | `isaac_bimanual_20260914_155625/bimanual/metrics.json` | 仅为 replay/试验配置的名义角色，尚未由真实任务语义确认。 |
| 末端静态间距 | `0.3121815343 m`；10.0011 s 内 min=max | `measured` | 同上 | 当前静态姿态的名义距离，不是轨迹最小安全距离。 |
| PhysX 末端位姿接口验证 | 左 `[0.0035805712, 0.1569913179, 0.2620288432] m`；右 `[0.0032817731, -0.1551592797, 0.2620157599] m`；间距 `0.3121507409 m` | `measured` | Isaac Script Editor：`OPENARM_PHYSX_EE_PROBE_OK` | `RigidPrim.get_world_poses(usd=False)` 可读取 PhysX link 位姿；用于下一次动态采集。 |
| 交接目标位置/姿态 | 未配置 | `not_configured` | 同上：`handoff_window=not_configured` | 尚无 marker、目标 TF 或姿态容差。 |
| 交接窗口 | 未配置 | `not_configured` | 同上 | 定义目标与容差后才能计算到达时间和窗口。 |
| 左右 action 同步偏差 | 未测 | `not_measured` | — | 现有有效控制试验只发送一条包含左右 J1 的共同 command；尚无每臂独立 action 时间戳序列。 |
| PhysX 动态末端采集 | `874` 样本；`15.0052971621 s` | `measured` | 最新 `isaac_bimanual_physx_*/bimanual/metrics.json` | 使用 `RigidPrim.get_world_poses(usd=False)`；采集期间执行三段左右 J1 共同 command。 |
| 动态末端间距 | 最小 `0.3019701336 m`；最大 `0.3111607593 m` | `measured` | 同上 | 当前三段 J1 轨迹的名义动态距离范围；最小值不是通用安全阈值。 |
| 动态相对速度 | 均值 `0.0004281507 m/s`；最大 `0.0381394014 m/s` | `measured` | 同上 | 由相邻 PhysX 末端相对位移除以采样时间间隔得到。 |
| 左右 action 同步方式 | 单条 shared bimanual command；独立 skew 未测 | `partial` | 同上 | 同一 ROS message 含左右 J1，不产生两臂独立到达时间。 |

## 控制

| 参数 | 当前值/状态 | 状态 | 证据 | 解释与限制 |
|---|---|---|---|---|
| state 关节映射 | 18 DOF：左右 J1--J7 交替，随后左/右各 2 finger | `measured` | `isaacsim_hold_stable_20260914_151311/control/idle_30s` | `/sim/openarm/joint_states` 已发布 name、position、velocity；`effort=[]`。 |
| state 吞吐 | 约 `40.0 Hz`；瞬时频率均值 `41.9969 Hz`，范围 `31.5170–53.9818 Hz` | `measured` | `isaacsim_hold_stable_20260914_151311/control/idle_metrics/metrics.json` | ROS 发布/录包频率，不等于 physics 或 articulation control tick。 |
| 静止 position 标准差 | 最大 `0.0 rad`（18 DOF） | `measured` | 同上 | `simulator_position_target_each_update` 的确定性硬保持结果。 |
| 静止 velocity 标准差 | 最大 `0.0 rad/s`（18 DOF） | `measured` | 同上 | 不代表自然动力学噪声或真机噪声。 |
| timestamped command subscriber | 已接收并执行左右 J1 command | `measured` | Isaac Script Editor：`OPENARM_COMMAND_CALLBACK`、`OPENARM_COMMAND_RECEIVED`、`OPENARM_COMMAND_APPLIED` | 输入 topic 为 `/sim/openarm/timestamped_joint_command`；仅控制当前 Isaac Sim articulation。 |
| command receipt | 基线试验 `1` 条；CLI 三段试验 `3` 条；固定轨迹试验 `3` 条；隔离 state v2 试验 `3` 条 | `measured` | `isaacsim_control_valid_20260915_095032/control/dynamic_test`；`isaacsim_control_track_20260915_095916/control/tracking_test`；`isaacsim_control_fixed_20260915_101449/control/fixed_tracking_test`；`isaacsim_control_hold_v2_20260915_105143/control/fixed_tracking_test` | `/sim/openarm/command_receipt`；receipt 中保存原 command 秒、纳秒。 |
| state feedback | 基线试验 `379` 条 / `11.7156 s`；CLI 三段试验 `652` 条 / `17.737045984 s`；固定轨迹试验 `659` 条 / `20.716404268 s`；隔离 state v2 试验 `628` 条 / `20.738195481 s` | `measured` | 同上 | 新试验使用隔离话题 `/sim/openarm/joint_states_v2`。 |
| command→receipt 延迟 | `0.661345707 s` | `partial` | `isaacsim_control_valid_20260915_095032/control/latency_metrics.json` | 从 publisher 写入的 command header 到 Isaac receipt header；包含 `ros2 topic pub` 启动/等待订阅匹配、DDS 传输与 callback 调度，不能作为纯 physics 延迟。 |
| receipt→首条 state | `0.014050445 s` | `measured` | 同上 | 表示 receipt 后首次 state 发布的时间差。 |
| command→首条 state | `0.675396152 s` | `partial` | 同上 | 与 command→receipt 相同地包含 CLI/DDS 侧时延。 |
| 闭环证据 | `true` | `measured` | 同上 | 同一 bag 中 receipt=1、state=379；command topic 本身未录到。 |
| command topic bag 记录 | 基线试验 `0` 条；CLI 三段试验 `2/3` 条；固定轨迹试验 `3/3` 条；隔离 state v2 试验 `3/3` 条 | `measured` | 同上 | 隔离 state v2 试验的 command、receipt、state 均完整录入。 |
| 三段双臂 J1 动态试验 | 目标序列：`[-0.0261804564, 0.0271758609]` → `[-0.0061804564, 0.0071758609]` → `[-0.0261804564, 0.0271758609] rad` | `measured` | `isaacsim_control_track_20260915_095916/control/tracking_test` | 每个目标同时作用于左右 J1；相邻 command 间约 2 s。 |
| 三段试验时长与消息数 | `17.737045984 s`；receipt `3` 条；state `652` 条；command 原文 `2` 条 | `partial` | 同上 | receipt 和 state 均完整；首条 command 原文未录到。 |
| 动态 state 平均频率 | `36.7025874 Hz` | `measured` | `isaacsim_control_track_20260915_095916/control/tracking_metrics.json` | ROS state 发布频率，不等于 physics/control tick。 |
| 第 1 段跟踪 | command→receipt `0.658471992 s`；receipt→首条 state `0.014670232 s`；初始误差 left/right `0.0187877109 / 0.0206288350 rad`；最终误差 `0.0188434534 / 0.0195977180 rad` | `partial` | 同上 | `0.002 rad` 容差未在该段窗口内达到。 |
| 第 2 段跟踪 | command→receipt `0.662689621 s`；receipt→首条 state `0.000495669 s`；初始误差 `0.0011565466 / 0.0004022820 rad`；最终误差 `0.0030859490 / 0.0031668041 rad`；首次容差时刻 `0.663185290 s` | `partial` | 同上 | command 发出时已在 `0.002 rad` 容差内，不能当作完整阶跃到达时间。 |
| 第 3 段跟踪 | command→receipt `0.663781201 s`；receipt→首条 state `0.015496163 s`；初始误差 `0.0169140510 / 0.0168331959 rad`；最终误差 `0.0141869914 / 0.0150375594 rad` | `partial` | 同上 | `0.002 rad` 容差未在该段窗口内达到。 |
| 固定轨迹试验 | A → B → A；目标分别为 `[-0.0261804564, 0.0271758609]`、`[-0.0061804564, 0.0071758609]`、`[-0.0261804564, 0.0271758609] rad` | `measured` | `isaacsim_control_fixed_20260915_101449/control/fixed_tracking_test` | 固定 ROS 发布器在匹配两个订阅者后发出三条 command。 |
| 固定轨迹消息完整性 | command `3` 条；receipt `3` 条；state `659` 条；总时长 `20.716404268 s` | `measured` | 同上 | 可作为当前闭环跟踪试验的完整 bag。 |
| 固定轨迹 state 平均频率 | `31.7622496 Hz` | `measured` | `isaacsim_control_fixed_20260915_101449/control/fixed_tracking_metrics.json` | ROS state 发布频率，不等于 physics/control tick。 |
| 固定轨迹第 1 段 A 跟踪 | command→receipt `0.008962773 s`；receipt→首条 state `0.000288612 s`；初始误差 left/right `0.0164483432 / 0.0180843905 rad`；最终误差 `0.0164309405 / 0.0151675525 rad` | `partial` | 同上 | 未达到 `0.002 rad` 容差。 |
| 固定轨迹第 2 段 B 跟踪 | command→receipt `0.021867461 s`；receipt→首条 state `0.000550299 s`；初始误差 `0.0035690595 / 0.0048324475 rad`；最终误差 `0.0028018434 / 0.0002815989 rad`；首次达到容差 `1.483609515 s` | `partial` | 同上 | 两关节曾同时达到容差；该段结束时 left J1 又高于容差。 |
| 固定轨迹第 3 段 A 跟踪 | command→receipt `0.027949552 s`；receipt→首条 state `0.000303953 s`；初始误差 `0.0171981566 / 0.0202815989 rad`；最终误差 `0.0151743693 / 0.0175046189 rad` | `partial` | 同上 | 未达到 `0.002 rad` 容差。 |
| 隔离 state v2 固定轨迹 bag | command `3` 条；receipt `3` 条；`/sim/openarm/joint_states_v2` 为 `628` 条；总时长 `20.738195481 s` | `measured` | `isaacsim_control_hold_v2_20260915_105143/control/fixed_tracking_test` | state topic 已与旧 `/sim/openarm/joint_states` 隔离，当前 bag 可用于跟踪分析。 |
| 隔离 state v2 平均吞吐 | `30.2339760 Hz` | `measured` | `isaacsim_control_hold_v2_20260915_105143/control/fixed_tracking_metrics.json` | 由相邻 state 时间戳的瞬时频率求均值；是 ROS state 吞吐，不等于 physics/control tick。 |
| 隔离 state v2 第 1 段 A 跟踪 | command→receipt `0.002915511 s`；receipt→首条 state `0.000781162 s`；初始误差 left/right `0.0175441038 / 0.0202217330 rad`；最终误差 `0.0133158155 / 0.0135637312 rad` | `partial` | 同上 | `0.002 rad` 容差未达到。 |
| 隔离 state v2 第 2 段 B 跟踪 | command→receipt `0.028493672 s`；receipt→首条 state `0.000860641 s`；初始误差 `0.0066841845 / 0.0064362688 rad`；最终误差 `0.0022176164 / 0.0000723502 rad`；首次同时达到容差 `1.178459901 s` | `partial` | 同上 | 曾同时达到 `0.002 rad`；本段结束时 left J1 高于容差。 |
| 隔离 state v2 第 3 段 A 跟踪 | command→receipt `0.029903812 s`；receipt→首条 state `0.000927287 s`；初始误差 `0.0177823836 / 0.0200723502 rad`；最终误差 `0.0177407730 / 0.0191630343 rad` | `partial` | 同上 | `0.002 rad` 容差未达到。 |
| Isaac 右 J7 position-drive 修复后 sim-only 跟踪 | `+0.02 rad` 终值 `0.0199395586 rad`，误差 `−0.0000604414 rad`；回零终值 `0.0000224130 rad`，误差 `0.0000224130 rad`；receipt `2/2` 为 `sim_sent=true`、`real_sent=false` | `measured` | `alignment/results/sim_only_router_after_j7_drive_repair.json` | J7 原 USD drive 为零 stiffness/damping；当前 Isaac-only live repair 使用 stiffness `100`、damping `10`、max force `7`。仅验证仿真闭环，未发送真机命令。 |
| 真实+Isaac 右 J7 `+0.02 rad` 配对试验 | target 段真机 `0.0040054932 rad`、仿真 `0.0199379269 rad`；真机/仿真误差 `−0.0159945068 / −0.0000620731 rad`；真机-仿真偏移 `−0.0159324337 rad`；回零段真机/仿真残差 `0.0036240177 / 0.0000252591 rad`；router 与 Isaac receipt 各 `2` 条 | `measured` | `alignment/results/openarm_real_sim_right_j7_step_0p02_v1/metrics.json` | 唯一一次获授权的真实动作。router 每次均报告 `sim_and_real_sent`；仿真达标，真机未跟至目标。真机路由已在试验后停止；该样本用于诊断，不可直接拟合或自动应用动作残差。 |
| 真实+Isaac 右 J7 相对 `+0.01 rad` 配对试验 | 初始/return 真机 `0.0036240177 rad`；target 真机仍 `0.0036240177 rad`，误差 `−0.0100000000 rad`；target 仿真 `0.0135898264 rad`，误差 `−0.0000341913 rad`；真机-仿真偏移 `−0.0099658087 rad`；router receipt `2/2` 均 `sim_and_real_sent` | `measured` | `alignment/results/openarm_real_sim_right_j7_relative_plus_0p01_v1/metrics.json` | 第二条获授权的真实动作；相对目标由实时真机 state 解析为 `0.0136240177 rad`，并在 2 s 后返回初始值。真机在整个 target 段未出现可测偏移，Isaac 达标；real router 已停止。 |
| 真机右 J4--J7 直接连续位置命令 | 以 `50 Hz`、`3 s` 流式目标 `0.1 rad`：J7/J6/J5/J4 的 `/joint_states` feedback=`0.0768673228 / 0.0864042115 / 0.0890745403 / 0.0940337224 rad` | `measured` | `alignment/results/manual_right_joints_0p1_streaming_20260915.json` | 指令为各轴绝对目标：保持其余六轴起点，仅将所选轴设为 `0.1 rad`，连续发布后返回起点。操作员已观察到 J4--J6 的明显真实关节运动，因此这是有效的真机动作协议；J7 的可见输出仍需单独确认。1 s 回程对 J5/J6 未完全收敛，不能作为回零验收。 |
| 真机编码器+Isaac 右 J7 `+0.1 rad` 流式配对试验 | endpoint=`0.0952315557 rad`；target 段真机 `/joint_states` / 仿真=`0.0738155184 / 0.0948796049 rad`；按当前未校准数值计算的误差=`−0.0214160372 / −0.0003519508 rad`；回程残差=`0.0019073777 / 0.0001251647 rad`；router receipt `20/20` accepted 且双端 sent | `partial` | `alignment/results/openarm_real_sim_right_j7_streamed_plus_0p1_v2/metrics.json` | 验证 Agent 可通过 canonical command→50 Hz router 驱动真机电机侧反馈和 Isaac。操作员未观察到明显真机输出关节运动；由于 motor→joint 的比例、符号、零偏尚未标定，不能将当前真机数值与 Isaac joint rad 直接相减，也不能用于延迟、增益或残差建模。 |
| Isaac 全 14 轴固定点基线（修复后） | 每轴绝对目标 `0.1 rad`；14/14 达到 `0.01 rad` 阈值；最大目标误差 `0.0011548236 rad`，最大回程误差 `0.0024683543 rad` | `measured` | `alignment/results/openarm_sim_only_bimanual_fixed_0p1_baseline_v1/*.json` | `enable_real=false`，未给真机发送命令。全臂 position drive 修复后 Isaac 已可作为双端固定点测量端点；不能据此推断真机性能。 |
| 真机+Isaac 全 14 轴固定点基线（v2） | 每轴绝对目标 `0.1 rad`、50 Hz、3 s hold、返回实时起点；router receipt `28/28` accepted 且双端 sent；14/14 Isaac 跟踪通过。真机目标误差 mean/mean-abs/max-abs=`−0.0129418304 / 0.0136154073 / 0.0265659571 rad`；Isaac=`−0.0003723088 / 0.0004074100 / 0.0011824057 rad`；真机−Isaac target gap mean/mean-abs/max-abs=`−0.0125695216 / 0.0132343172 / 0.0265269697 rad`；真机回程误差最大 `0.0179293507 rad`。 | `partial` | `alignment/results/openarm_real_sim_bimanual_fixed_0p1_full14_v2/*.json` | 全 14 轴已实际串行执行并自动关闭 real router；当前值是同一 ROS joint 坐标的控制跟踪差异。J4--J6 已有操作员视觉动作确认；若用于机构输出角或学习残差，仍需每轴外部视觉/传动标定与重复试验。 |
| physics/control tick | 未测 | `not_measured` | — | state 吞吐不能替代此参数。 |

## 下一次更新顺序

1. 完成 physics/control tick 与独立左右 receipt skew，并将有效输出写入本表；顶视任务相机采集已完成。
2. 定义任务交接目标位置/姿态及容差后，采集交接窗口；无任务目标时该项保持 `not_configured`。
3. 控制：以“单轴绝对 `0.1 rad`、50 Hz、3 s hold、返回起点”的已验证协议逐轴测量。J4--J6 已有操作员视觉确认；J7 要先补充同样的可见运动证据。然后再用同一目标和采样窗口比较真机与 Isaac，当前 J7 单一样本仍不能标定残差。
