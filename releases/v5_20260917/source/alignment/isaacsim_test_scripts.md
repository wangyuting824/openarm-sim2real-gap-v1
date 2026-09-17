# Isaac Sim 可复用测试脚本

本文件只记录测试程序、运行位置、输入输出及迁移到其他机械臂时需要替换的配置。测量数值写入 `isaacsim_measurement_log.md`；故障、无效试次和修复过程写入 `README.md`。

## 通用运行环境

宿主机结果目录：`$HOME/openarm_ws/alignment/results/isaacsim_migration`。

ROS 命令均在容器 `openarm-sim-ros` 中执行，并先加载：

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/openarm/fastdds_udp.xml
```

## 迁移到另一台机械臂时的配置

| 配置项 | 当前 OpenArm 值 | 新机械臂需要替换的位置 |
|---|---|---|
| articulation root | `/openarm_v20/Geometry/world/openarm_body_link0` | `isaacsim_timestamped_command_bridge.py` 的 `ROOT` |
| 左右末端 prim | `openarm_left/right_ee_base_link` 的完整 USD 路径 | `isaacsim_capture_bimanual_metrics.py` 的 `LEFT_EE_PRIM`、`RIGHT_EE_PRIM` |
| command/receipt topic | `/sim/openarm/timestamped_joint_command`、`/sim/openarm/command_receipt` | bridge、发布器和分析命令中的 topic |
| 隔离 state topic | `/sim/openarm/joint_states_v2` | state publisher 的 `STATE_TOPIC`、录包 topic 与分析器 `--state-topic` |
| 轨迹关节名和目标 | `openarm_left/right_joint1` 与 A/B 值 | `publish_fixed_j1_trajectory.py` 的 `JOINT_NAMES`、`PHASES` |
| 结果目录前缀 | `isaacsim_*` | 按新机械臂名称替换，避免混写结果 |

开始前先在 Isaac Sim 加载新机械臂 USD、确认 articulation 已初始化，并从 `/sim/.../joint_states` 核对关节名和顺序。

## 脚本目录

| 脚本 | 运行位置 | 作用 | 输出 |
|---|---|---|---|
| `isaacsim_timestamped_command_bridge.py` | Isaac Sim Script Editor | ROS command → articulation position target；发布 receipt | command、receipt topic |
| `isaacsim_publish_openarm_joint_state.py` | Isaac Sim Script Editor | 从 articulation 发布压平后的 18-DOF `JointState` 到隔离 state topic | `/sim/openarm/joint_states_v2` |
| `publish_fixed_j1_trajectory.py` | ROS Docker 容器 | A→B→A 固定轨迹；发布前等待 bridge 与 recorder | 三条 timestamped command |
| `analyze_tracking_bag.py` | ROS Docker 容器 | 每段 command、receipt、state 跟踪分析 | `fixed_tracking_metrics.json` |
| `analyze_control_dynamic_bag.py` | ROS Docker 容器 | 单次/动态 command 闭环延迟分析 | `latency_metrics.json` |
| `analyze_ros2_joint_state_bag.py` | ROS Docker 容器 | JointState 吞吐和逐关节统计 | `metrics.json`、`joint_stats.csv` |
| `isaacsim_capture_bimanual_metrics.py` | Isaac Sim Script Editor | 采集末端距离、相对速度、交接窗口 | `bimanual/metrics.json`、CSV |
| `isaacsim_capture_handoff_window.py` | Isaac Sim Script Editor | 以 PhysX 末端位姿按任务目标计算交接窗口 | `bimanual/handoff_metrics.json`、CSV |
| `isaacsim_capture_camera_params.py` | Isaac Sim Script Editor | 枚举 Camera prim 参数和世界位姿 | `vision/camera_params.json` |
| `isaacsim_capture_task_camera.py` | Isaac Sim Script Editor | 创建任务相机、保存 RGB 帧、内参及帧时间戳 | `vision/frames/`、`camera_info.json`、CSV |
| `isaacsim_measure_physics_tick.py` | Isaac Sim Script Editor | 分别测 PhysX physics-step 与 Kit update 频率 | `control/tick_metrics.json` |
| `publish_independent_j1_skew.py` | ROS Docker 容器 | 分别发送左右 J1 command | 两条 timestamped command |
| `analyze_independent_action_skew.py` | ROS Docker 容器 | 按 receipt 时间戳计算独立 command skew | `independent_action_skew.json` |
| `isaacsim_hold_openarm_position.py` | Isaac Sim Script Editor | 静止 position-hold 基线 | 配合 state bag 使用 |
| `isaacsim_ros2_joint_state_probe.py` | Isaac Sim Script Editor | DDS/ROS 2 JointState 连通性探针 | `/sim/openarm/joint_states_probe` |
| `publish_timestamped_bimanual_test.py` | ROS Docker 容器 | 单条双臂 command 冒烟测试 | 一条 timestamped command |

## 1. 持续 position-target 桥接

在 Isaac Sim Script Editor 运行：

```python
exec(compile(open(
    "/home/tangyuan/openarm_ws/alignment/isaacsim_timestamped_command_bridge.py",
    encoding="utf-8",
).read(), "/home/tangyuan/openarm_ws/alignment/isaacsim_timestamped_command_bridge.py", "exec"))
```

成功标志：

```text
OPENARM_TIMESTAMPED_BRIDGE_ARMED
OPENARM_TIMESTAMPED_BRIDGE_READY dofs=18
```

每条 command 后应依次出现 `OPENARM_COMMAND_CALLBACK`、`OPENARM_COMMAND_RECEIVED`、`OPENARM_COMMAND_ACCEPTED`、`OPENARM_COMMAND_APPLIED`。若保持超过 240 个 update，还会出现 `OPENARM_POSITION_TARGET_HELD`。桥接保存最近一次目标，并在每个 Isaac update 调用 `apply_action`。

## 2. 21 秒固定轨迹录包

在宿主机终端运行。该时长覆盖 recorder 就绪、三段各 4 秒的 A→B→A 轨迹和最后一段 state 反馈。

```bash
SESSION_ID="isaacsim_control_fixed_$(date +%Y%m%d_%H%M%S)"
SESSION="$HOME/openarm_ws/alignment/results/isaacsim_migration/$SESSION_ID"
mkdir -p "$SESSION/control"

docker cp "$HOME/openarm_ws/alignment/publish_fixed_j1_trajectory.py" \
  "openarm-sim-ros:/tmp/publish_fixed_j1_trajectory.py"

docker exec -e SESSION_ID="$SESSION_ID" -d openarm-sim-ros bash -lc '
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/openarm/fastdds_udp.xml
mkdir -p "/tmp/${SESSION_ID}"
exec timeout -s INT 21s ros2 bag record \
  -o "/tmp/${SESSION_ID}/fixed_tracking_test" \
  --topics \
  /sim/openarm/timestamped_joint_command \
  /sim/openarm/command_receipt \
  /sim/openarm/joint_states_v2
'

sleep 3

docker exec -it openarm-sim-ros bash -lc '
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/openarm/fastdds_udp.xml
python3 /tmp/publish_fixed_j1_trajectory.py
'

sleep 12

docker exec -it openarm-sim-ros bash -lc \
  "source /opt/ros/jazzy/setup.bash && ros2 bag info /tmp/${SESSION_ID}/fixed_tracking_test"

docker cp "openarm-sim-ros:/tmp/${SESSION_ID}/fixed_tracking_test" \
  "$SESSION/control/fixed_tracking_test"

echo "SESSION=$SESSION"
```

验收前提：`timestamped_joint_command`、`command_receipt` 均为 `3` 条，且 `/sim/openarm/joint_states_v2` 非零。不要将旧 `/sim/openarm/joint_states` 与该试验混用。

## 3. 固定轨迹跟踪分析

在宿主机终端运行：

```bash
SESSION_ID="填入上一节输出的 session 名称"
SESSION="$HOME/openarm_ws/alignment/results/isaacsim_migration/$SESSION_ID"

docker cp "$HOME/openarm_ws/alignment/analyze_tracking_bag.py" \
  "openarm-sim-ros:/tmp/analyze_tracking_bag.py"

docker exec -it openarm-sim-ros bash -lc "
source /opt/ros/jazzy/setup.bash
python3 /tmp/analyze_tracking_bag.py \
  /tmp/$SESSION_ID/fixed_tracking_test \
  --output /tmp/$SESSION_ID/fixed_tracking_metrics.json \
  --tolerance-rad 0.002 \
  --state-topic /sim/openarm/joint_states_v2
"

docker cp "openarm-sim-ros:/tmp/$SESSION_ID/fixed_tracking_metrics.json" \
  "$SESSION/control/fixed_tracking_metrics.json"
```

输出逐段提供 command→receipt、receipt→首条 state、初始/最终绝对误差及首次达到容差时间。

分析器会根据 raw command 与 receipt 的计数生成不同的 `limitations` 字段；两者均为 3 时，不能写“首条 command 缺失”。

## 3.1 隔离 state v2 发布器

在运行 bridge 后，于 Isaac Sim Script Editor 运行：

```python
exec(compile(open(
    "/home/tangyuan/openarm_ws/alignment/isaacsim_publish_openarm_joint_state.py",
    encoding="utf-8",
).read(), "/home/tangyuan/openarm_ws/alignment/isaacsim_publish_openarm_joint_state.py", "exec"))
```

成功标志为 `OPENARM_STATE_PUBLISHER_ARMED`、`OPENARM_STATE_PUBLISHER_READY dofs=18` 和 `OPENARM_STATE_PUBLISHED`。该脚本使用 `np.asarray(...).reshape(-1)`，因此可处理 Isaac 返回的 `(1, DOF)` position/velocity 数组。迁移时只修改 `ROOT`、`STATE_TOPIC` 和 `PUBLISH_HZ`；录包及分析命令必须使用同一 `STATE_TOPIC`。

## 4. 双臂末端动态采集

在 Isaac Sim Script Editor 加载并运行 `isaacsim_capture_bimanual_metrics.py`。迁移机械臂前需替换脚本顶部的左右末端 USD prim 路径。动态采集必须从 PhysX 读取位姿；当前复用版本应使用 `RigidPrim.get_world_poses(usd=False)`，不能用 USD `XformCache` 代替。

## 4.1 physics/control tick

在 Timeline 已播放、bridge 和 state publisher 已加载时，Isaac Sim Script Editor 运行：

```python
exec(compile(open(
    "/home/tangyuan/openarm_ws/alignment/isaacsim_measure_physics_tick.py",
    encoding="utf-8",
).read(), "/home/tangyuan/openarm_ws/alignment/isaacsim_measure_physics_tick.py", "exec"))
```

10 秒后 Console 输出 `OPENARM_PHYSICS_TICK_COMPLETE` 和 `RESULT=.../control/tick_metrics.json`。以 `physics_step.mean_hz` 记录 physics tick，以 `kit_update.mean_hz` 记录脚本更新频率；两者需要分开填写。

## 4.2 独立左右 command receipt skew

该试验在同一个进程中连续发布一条 left J1 与一条 right J1 command，`INTER_COMMAND_S=0.0`。record 先于发布器启动，确保完整录入。

```bash
SESSION_ID="isaacsim_independent_skew_$(date +%Y%m%d_%H%M%S)"
SESSION="$HOME/openarm_ws/alignment/results/isaacsim_migration/$SESSION_ID"
mkdir -p "$SESSION/control"

docker cp "$HOME/openarm_ws/alignment/publish_independent_j1_skew.py" \
  "openarm-sim-ros:/tmp/publish_independent_j1_skew.py"
docker cp "$HOME/openarm_ws/alignment/analyze_independent_action_skew.py" \
  "openarm-sim-ros:/tmp/analyze_independent_action_skew.py"

docker exec -e SESSION_ID="$SESSION_ID" -d openarm-sim-ros bash -lc '
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/openarm/fastdds_udp.xml
mkdir -p "/tmp/${SESSION_ID}"
exec timeout -s INT 8s ros2 bag record -o "/tmp/${SESSION_ID}/independent_skew" --topics \
  /sim/openarm/timestamped_joint_command \
  /sim/openarm/command_receipt
'

sleep 2
docker exec -it openarm-sim-ros bash -lc '
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/openarm/fastdds_udp.xml
python3 /tmp/publish_independent_j1_skew.py
'
sleep 4

docker exec -it openarm-sim-ros bash -lc "source /opt/ros/jazzy/setup.bash && \
  python3 /tmp/analyze_independent_action_skew.py /tmp/$SESSION_ID/independent_skew \
  --output /tmp/$SESSION_ID/independent_action_skew.json"
docker cp "openarm-sim-ros:/tmp/$SESSION_ID/independent_skew" "$SESSION/control/independent_skew"
docker cp "openarm-sim-ros:/tmp/$SESSION_ID/independent_action_skew.json" \
  "$SESSION/control/independent_action_skew.json"
echo "SESSION=$SESSION"
```

验收前提：command、receipt 均为两条，且每条只包含一个关节。输出的 `independent_receipt_skew_s` 是两条 Isaac receipt 时间戳之差，不是双臂末端到位 skew。

## 4.3 交接目标、姿态容差与窗口

先按任务定义填写 `isaacsim_capture_handoff_window.py` 顶部的 `HANDOFF_TARGET_M`、`HANDOFF_TARGET_XYZW`、`POSITION_TOLERANCE_M` 和 `ORIENTATION_TOLERANCE_RAD`。目标必须是双方实际要共同到达的 World 坐标和姿态；不能用当前两末端中点代替任务定义。

```python
exec(compile(open(
    "/home/tangyuan/openarm_ws/alignment/isaacsim_capture_handoff_window.py",
    encoding="utf-8",
).read(), "/home/tangyuan/openarm_ws/alignment/isaacsim_capture_handoff_window.py", "exec"))
```

启动后先执行能让两臂接近交接点的既定任务轨迹。12 秒后输出 `handoff_metrics.json`；其中每个 `handoff_windows_s` 条目的 start/end 是两末端在同一 PhysX 样本内同时满足位置与姿态容差的连续区间。

## 5. 视觉参数盘点

在 Isaac Sim Script Editor 加载并运行 `isaacsim_capture_camera_params.py`。该脚本只枚举当前 stage 的 Camera prim；任务图像、Render Product、CameraInfo 与帧时间戳需要在任务相机创建后另行采集。

## 5.1 任务相机、内参和图像帧

默认配置创建名为 `ceiling` 的顶视相机：位置 `[0, 0, 1.20] m`，朝向 `[0, 0, 0.25] m`，分辨率 `640×480`，请求 `30 Hz`、持续 `10 s`。运行前可在脚本顶部修改 `CAMERA_ID`、`POSITION_M`、`LOOK_AT_M`、`RESOLUTION` 和 `FPS`。

```python
exec(compile(open(
    "/home/tangyuan/openarm_ws/alignment/isaacsim_capture_task_camera.py",
    encoding="utf-8",
).read(), "/home/tangyuan/openarm_ws/alignment/isaacsim_capture_task_camera.py", "exec"))
```

Console 应依次出现 `OPENARM_TASK_CAMERA_ARMED`、`OPENARM_TASK_CAMERA_READY`、`OPENARM_TASK_CAMERA_FRAME_CAPTURED` 和 `OPENARM_TASK_CAMERA_COMPLETE`。结果目录包含 `camera_info.json`、`frame_timestamps.csv`、`frames/*.png`、`render_conditions.json` 和 `camera_capture_metrics.json`。内参由 USD 焦距、光圈和分辨率换算；畸变模型为零畸变的 `plumb_bob`，是仿真配置而非真机标定。`render_conditions.json` 枚举当前灯光，并明确记录曝光、背景、遮挡和图像噪声的配置状态。
