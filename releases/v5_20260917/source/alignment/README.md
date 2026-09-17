# OpenArm 仿真与真机对齐工作记录

最后更新：2026-09-09（Asia/Shanghai）

## 目标与更新约定

在数据采集前，核对真机、机器人模型和仿真的关节定义、运动范围与相机坐标关系。用 RViz 检查运动学姿态；动力学一致性需要在实际仿真器中另行验证。

本文件作为本次工作的持续记录。后续每次发现问题、完成排查、修改配置或取得验证结果后，同步更新“问题与解决方案”“当前状态”和“下一步”。记录区分已确认事实、待核对事项与拟议方案，不把方案当作已完成工作。文件不会自动后台更新，由后续执行工作的助手或人员维护。

## 当前状态

- 已启动 RViz、`robot_state_publisher` 和 `joint_state_publisher_gui`；启动日志显示模型初始化、关节滑块配置和 OpenGL 初始化成功。尚未完成逐关节视觉验收。
- 当前模型：OpenArm V2，`default_bimanual` 预设；真机版本和夹爪型号仍需现场确认。
- 当前为模型显示模式，未通过此次启动连接或使能真机电机。
- 当前关节状态来自 GUI 滑块，不能当作真机反馈或采集观测值。
- 2026-09-09 17:00 已另行启动 KER → MuJoCo 流程。日志确认 KER USB 连接成功、所有 Dora 节点就绪、五路相机初始化、仿真事件循环启动；等待人工逐关节跟随核对。原 RViz 仍由 GUI 驱动，未接入此数据流。
- 上一轮仿真会话目录（相对工作区）：`dora/dora-openarm-data-collection/ker_mujoco_data/20260909-170054-8393cda8/`。未主动开始录制 episode，未启动真机控制；该会话及其孤立 Dora 子进程已在本次操作中退出。
- 已生成 [关节对照表 CSV](joint_alignment_checklist.csv)，预填最终展开 URDF 中的模型信息及 KER 手臂限位，真机字段标为“待核对”。
- 表中有 18 个活动关节条目，包含夹爪从动关节，不等于 18 个独立电机。
- 已保存同参数展开的 [参考 URDF](openarm_v20_reference.urdf)。该文件是本次快照；源配置变化后需要重新生成，并同步 CSV。

## RViz 启动方式

在工作区终端执行以下命令；已有窗口运行时无需重复启动：

```bash
source /opt/ros/jazzy/setup.bash
source /home/tangyuan/openarm_ws/install/setup.bash
ros2 launch openarm_description display_openarm.launch.py arm_type:=v20 robot_preset:=default_bimanual
```

启动文件：[display_openarm.launch.py](../src/openarm_description/launch/display_openarm.launch.py)。此显示入口只启动模型与可视化节点。

注意：现有真机硬件插件的 `on_activate()` 会执行 `enable_all()` 和 `return_to_zero()`。不能直接把真机 bringup 当作只读反馈入口。接入真实反馈之前，应先实现并验证只读启动路径。

## 关节对照表应包含什么

每个关节一行，左右臂分别记录；从动关节注明 mimic 关系，不强行分配独立电机 ID。

| 类别 | 字段 | 核对目的 |
| --- | --- | --- |
| 关节身份 | 左右臂、关节名称、关节类型、父连杆、子连杆、CAN 接口、电机 ID、型号 | 模型关节与实体电机一一对应 |
| 零位与方向 | 模型旋转轴、模型原点 xyz/rpy、真机零位姿态、方向符号、电机零位偏置 | 排查反转、坐标定义和整体角度偏移 |
| 角度换算 | 反馈单位、反馈属于电机轴还是输出轴、减速比 | 确保模型与真机使用同一关节坐标 |
| 位置限位 | URDF、KER、仿真、机械实际上下限、电机配置位置上下限、最终软件上下限 | 区分各层范围及其依据 |
| 运动与驱动限制 | URDF 速度与力矩/力限值、电机配置速度、电流或力矩限值 | 核对配置及后续运行约束 |
| 验证记录 | 正方向、零位、多姿态核对结果、测量依据、备注 | 区分模型配置值和现场验证值 |

填写规则：

- ROS 旋转关节使用 rad，便于人工核对时另列 deg；平移关节使用 m。速度与力矩/电流必须写清单位，不能直接混比。
- 零位必须描述实际连杆姿态，不能仅填“0”。GUI 的居中位置不一定是零位。
- 普通旋转关节可按 `q = sign × (电机角度 − 电机零位) / 减速比` 理解；若反馈已是输出轴角度，不要重复除减速比。
- 电机协议的数值编码范围不等于机构允许运动范围。
- 最终软件范围应位于机械范围与换算后的电机允许范围内，并留出适当余量；当前不臆定余量数值。
- 左右臂涉及镜像处理，应使用最终展开 URDF 核对，不能只看共用 YAML。
- 未测量或未核实的数据保留“待核对”，不要用模型值冒充实测值。确认不适用的字段填写“不适用”并说明原因。

## 怎样确定对应关系、零位和正方向

这三项是模型与真机之间的对照，不是只确认其中一侧。先记录模型定义，再确认实体关节和真实反馈与该定义的关系。模型是当前待验证的参考；如果模型与实际装配不一致，应查明原因后修正模型或映射，不能默认模型一定正确。

### 关节对应关系

1. 在 GUI 中只改变一个关节，例如 `openarm_right_joint1`，观察它的父子连杆和转轴位置。下游连杆整体跟随属于正常现象，识别的是两段连杆之间发生相对转动的位置。
2. 在真机上找到结构位置相同的转轴，核对安装标识、接线及驱动配置中的 CAN 接口、电机 ID。J1 不一定对应 CAN ID 1。
3. 当前显示模式不能验证电机 ID 的实际对应。若需要以运动确认，必须等真机反馈和可控操作路径准备完成后，逐关节小幅验证；仅从配置查到的值标记为“配置对应，未实测”。

### 零位

- 模型零位是 URDF 中该关节变量 `q=0` 时的父子连杆相对姿态，仍包含 joint origin 的固定变换；不意味着整条手臂一定竖直或伸直。GUI 的居中按钮可能使用限位中点，不可代替输入 0。
- 记录模型在 q=0 时两侧连杆的相对朝向，可使用姿态描述和参考照片编号。先统一观察方位，避免左右镜像造成误判。
- 真机需要确认：实体处于对应参考姿态时，原始电机反馈是多少，转换后的关节反馈是否为 0。这是模型零位与编码器读数的映射关系；编码器数值 0 不自动代表 URDF 零位。
- 第一轮只核对和记录，不为了让数字变成 0 而直接执行电机清零、回零或写编码器参数。只有明确当前反馈单位、方向、轴端和减速比后，才能确定偏置。

### 正方向

- 模型中从一个合法角度小幅增加 q，观察连杆相对父连杆的转动方向。旋转轴以关节坐标系表达，正向遵循右手规则；单写“顺时针”不够，需注明观察方向。
- 真机在对应物理方向的小幅运动中，记录原始反馈和转换后的关节反馈增减。与模型正向相同的实体运动，应使最终 ROS 关节角 q 增加。
- 若原始电机反馈减小，可能需要方向符号 -1，但先排查驱动是否已反向、映射是否已处理，以及所观察的电机 ID 是否正确，避免重复取反。
- GUI 滑块增加只能验证模型方向，不能证明真机反馈方向正确。当前未接入真机，本轮只能完成模型侧记录与实体结构静态对照。

建议验证记录使用明确结论，例如“模型已确认；真机待核对”，而不是在只观察模型后填“通过”。先选一个关节走通对应、零位、方向的完整过程，再扩展到全部关节。

## 消息链路与接口

当前显示链路：

```text
joint_state_publisher_gui → /joint_states → robot_state_publisher → /tf、/tf_static → RViz
                                               ↑
                                              URDF
```

计划中的真实反馈链路：

```text
电机反馈 → CAN → openarm_hardware → ros2_control 状态接口
                                      ↓
                            joint_state_broadcaster
                                      ↓
                               /joint_states
                                      ↓
                           robot_state_publisher → TF → RViz
```

现有工程已包含状态广播器、状态发布器和控制器。只有缺少标准接口或需要仿真数据转换时才新增桥接节点；一个节点可以同时订阅和发布。

| 用途 | 接口示例 | 消息或 Action 类型 |
| --- | --- | --- |
| 关节状态 | `/joint_states` | `sensor_msgs/msg/JointState` |
| 坐标变换 | `/tf`、`/tf_static` | `tf2_msgs/msg/TFMessage` |
| 轨迹命令 | `/left_joint_trajectory_controller/joint_trajectory` | `trajectory_msgs/msg/JointTrajectory` |
| 带执行反馈的轨迹请求 | `…/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` |
| Forward 控制器命令 | `…/commands` | `std_msgs/msg/Float64MultiArray` |
| 相机图像 | `/camera/image_raw` | `sensor_msgs/msg/Image` |
| 相机内参 | `/camera/camera_info` | `sensor_msgs/msg/CameraInfo` |

具体话题取决于命名空间和已启动控制器。通信需要话题名称、类型、QoS 兼容，以及一致的 ROS 域和可用的网络发现。关节数据按 `JointState.name` 对应，不假定数组顺序固定。

接入真机反馈时，不能让 GUI 和真实状态源同时发布同一组关节的状态。若同时显示独立的仿真和真机模型，应隔离状态话题，并避免 TF frame 名称冲突。采集时区分命令与实测状态。

参考：[robot_state_publisher](https://index.ros.org/r/robot_state_publisher/)、[轨迹控制器接口](https://docs.ros.org/en/ros2_packages/rolling/api/joint_trajectory_controller/doc/userdoc.html)。实际行为仍以本机安装版本和配置为准。

## 问题与解决方案

| 编号 | 问题或发现 | 依据 | 当前结论 / 解决方案 | 状态与验证 |
| --- | --- | --- | --- | --- |
| A-001 | 首先需要启动 RViz 观察模型 | 显示 launch 及本次启动日志 | 使用 V2 双臂模型显示入口，已启动 RViz 和关节滑块 | 已启动；逐关节视觉核对待完成 |
| A-002 | J7 的模型与遥操作限位不同 | V2 模型约 ±90°；KER 配置约 ±60° | 可能是有意缩小的工作范围，先确认设计依据与真机范围，不直接扩大或统一 | 待核对；未修改限位 |
| A-003 | 左右臂镜像可能导致原始 YAML 与实际关节范围不同 | V2 Xacro 存在镜像轴和限位处理 | 使用最终展开 URDF 预填对照表，再核对真机零位和正方向 | 模型值已提取；真机待验证 |
| A-004 | 真机激活不是只读操作 | `openarm_simple_hardware.cpp` 的 `on_activate()` 调用使能和回零 | 接真实反馈前实现并验证只读启动路径 | 待实现；本次仅显示模型 |
| A-005 | KER J7 存在历史角度回绕问题 | 现有 `wjz-log/joint7_angle_wrap_fix.md` 和解绕代码 | 现有方案为先解绕，再换算和限位；此次未重新修改代码 | 已有修复记录；本轮未重新验证 |
| A-006 | 夹爪模型存在从动关节 | 展开 URDF 的 mimic 关系 | 对照表注明从动关系，区分模型关节数与独立电机数 | 已在表中注明；实体对应待确认 |

| A-007 | 遥操臂似乎只能连接真机或仿真之一 | 两套已有入口各自读取 USB | 单一 KER 读取节点分发目标；当前先复用 MuJoCo 入口 | KER 已连接；双端桥接待实现 |
| A-008 | 同一目标不代表真机与仿真实际状态同步 | 两端控制、延迟及动力学独立 | 分开记录公共目标、各端命令、反馈及图像，并对齐时间 | 设计已记录；双端采集待实现 |
| A-009 | MuJoCo 原始 Dora 数据流未向 ROS 发布实际关节观测 | 数据流只包含 Dora 内部 `arm_*_observation` 输出 | 新增 Dora→ROS bridge，发布 `/sim/joint_states`；新增只读监视器与 `/joint_states` 比较 | 已完成 8 秒短时运行验证；bridge、MuJoCo、KER 和其它节点均 ready，正常退出 |
| A-010 | 新增 Dora 节点首次直接 `dora run` 时 source 未构建 | Dora 报 `Could not find source path dora-openarm-ros2-bridge` | 启动脚本先执行 `dora build dataflow-ker-mujoco.yaml --uv`，再生成独立会话运行 | 已修复并通过完整 dataflow 构建 |
| A-011 | 当前已确认 MuJoCo 状态正常，但尚未确认真机 `/joint_states` | 2026-09-09 收到 `/sim/joint_states` 的 16 个关节状态；用户输出未出现 `/joint_states` 消息 | 先检查 ROS 话题、节点和真机状态广播器；在真机状态源出现前不做双端方向或限位结论 | MuJoCo 已通过；真机状态待接通 |
| A-012 | KER 难以保证一次只动一个关节，直接动态测限位会混入其它关节变化 | 用户操作反馈；MuJoCo 模型提供每个 hinge joint 的 `range` | 先用 `alignment/check_mujoco_limits.py` 对模型逐关节做下限/中点/上限数值扫描，再与已知机械限位表比较 | 已扫描 18 个关节；机械表尚未填写，结果为 `NEEDS_MECHANICAL_LIMITS` |
| A-013 | 限位扫描最初出现 `nan` 和 `unknown` | `alignment/mechanical_limits.csv` 原来只有表头 | 从 V2 arm、pinch-gripper 配置补入参考范围，并增加 `source_type`；`project_config` 不冒充机械实测 | 已重新扫描；结果为 `REFERENCE_ONLY`，待真机端点实测确认 |
| A-014 | 仓库没有完整的真机机械端点实测表 | 搜索 arm、gripper、CAN 和 KER 配置后，仅找到模型/软件范围及 J7 的 KER 约 ±60°记录 | 新增真机启动脚本和只读反馈范围记录器；将采样先标为 `measured_feedback`，确认机械端点后再改为 `measured_mechanical` | 工具已构建；尚未在真机上采样 |
| A-015 | 真机 `/joint_states` 尚未有输出，且检查命令写成了 `--oncece` | 用户终端 `ros2 topic info` 显示 `/joint_states` 的 Publisher count 为 0，只有对齐监视器、robot_state_publisher 和 CLI 订阅者 | 启动真实 `ros2_control_node` 和 `joint_state_broadcaster`；确认发布者出现后再运行记录器 | 已确认：真机状态源尚未启动 |
| A-016 | 真机启动脚本在加载 ROS workspace 时因 `COLCON_TRACE` 未定义退出 | `set -u` 在 `source install/setup.bash` 之前生效 | 将 workspace setup 放在 nounset 之前加载；脚本语法检查通过 | 已修复；尚未启动真机 |
| A-017 | 真机 bringup 默认同时打开 RViz，容易误以为只启动了可视化 | `openarm.bimanual.launch.py` 原先无 RViz 开关 | 增加 `use_rviz` 参数；真机脚本传 `use_rviz:=false`，控制器和硬件仍照常启动 | 已构建；未启动真机 |
| A-018 | 把 launch 参数逐行输入 Bash 导致“未找到命令” | `use_fake_hardware:=false`、`can0` 等本身不是 shell 命令 | 使用 `bash alignment/start_real_openarm.sh`，或把参数写在同一条 `ros2 launch` 命令后 | 已说明；之前的输入未启动真机 |
| A-019 | 控制器激活日志不能单独证明真机已连接 | `Successfully switched controllers` 只表示控制器启动；还需看到 `OpenArmHW`、CAN 初始化和 `/joint_states` 发布者 | 检查完整启动日志、CAN 接口、`/joint_states` 发布者和 `ros2_control_node`；无控制命令时机械臂不会主动运动 | 待用户提供完整日志与话题检查结果 |
| A-020 | `/joint_states` 已发布但 16 个位置全为 0，且 ROS 图提示重复节点名 | 状态广播器和控制器管理器已运行；全零可能是当前零位，也可能是 CAN 没有收到反馈；重复启动会混淆状态源 | 保留一个 bringup 实例，检查完整 `OpenArmHW`/CAN 日志和 CAN 接口，再观察静止反馈是否变化 | 已确认状态话题存在；硬件反馈有效性待验证 |
| A-021 | CAN 设备存在但未启用 | `can0/can1` 均为 `state DOWN`、`can state STOPPED` | 使用项目 `openarm-can-cli -i canX can_configure` 配置 CAN-FD（仲裁相位 1 Mbit/s、数据相位 5 Mbit/s）并置为 UP，再启动真机 bringup | 已定位；待现场执行 CAN 配置 |
| A-022 | 真机控制器在硬件激活完成前启动 | 日志显示双臂 `return_to_zero` 尚未完成时，spawner 已加载控制器并报 `Failed to configure controller`；原等待时间为 1 秒 | 将双臂 bringup 的控制器等待时间改为 7 秒，并重新构建 `openarm_bringup` | 已修复并构建；待真机复测 |
| A-023 | 手工 `ip link` 命令只设置了 1 Mbit/s，未体现 CAN-FD 5 Mbit/s 数据相位 | `openarm-can-cli can_configure` 的默认值是仲裁相位 1 Mbit/s、数据相位 5 Mbit/s、FD 开启；Linux 接口必须与之匹配 | 真机启动前继续使用 `openarm-can-cli -i can0 can_configure` 和 `-i can1 can_configure`；不再用省略 `dbitrate/fd on` 的简化命令 | 已澄清；此前简化命令已更正 |
| A-024 | CAN 正常但三个控制器 spawner 并发配置失败 | 新日志显示左右硬件均成功激活，三个 `TimerAction` 在同一时刻启动，控制器加载/资源声明发生竞争 | 将状态广播器、双臂位置控制器、夹爪控制器改为 7/8/9 秒串行启动 | 已修复并构建；待真机复测 |
| A-025 | 串行启动后仍提示控制器“already loaded”但随后“不存在” | 最新日志中第一个 spawner 就报告 `Controller already loaded`，而本次 launch 此前没有加载它，通常表示仍有旧的 `/controller_manager` 或旧 bringup 进程参与服务响应 | 完全关闭旧 bringup，确认只剩一个 `ros2_control_node` 和一个 `/controller_manager` 后再复测 | 待现场清理重复进程并验证 |
| A-026 | 真机右侧电机启动后抖动并有噪音 | 可能与回零目标、位置反馈无效/延迟、CAN ID 映射或重复命令有关；该现象具有机械风险 | 立即急停并退出 bringup；在确认原因前不继续限位测试，后续先做无运动的反馈与命令源检查 | 待现场提供停止后的日志和控制器话题信息 |
| A-027 | 机身持续震颤 | 当前 `OpenArmHW::on_activate()` 会使能电机并回零，`write()` 持续发送 MIT 位置控制；目标零位、反馈、增益或命令源任一不一致都可能产生振荡 | 立即急停并停止 bringup；在增加并验证只读/低风险激活路径前，不继续限位测试 | 待确认反馈有效性、零位和控制命令来源 |
| A-028 | 用户怀疑修改了 10000 Hz 导致震颤 | 当前 bringup 控制器 `update_rate` 是 50 Hz；仓库检索未发现 10000 Hz 设置。真机与仿真的主要差异是硬件插件、CAN、使能/回零和真实 MIT 闭环 | 先按 `use_fake_hardware`、插件日志和 CAN 状态区分模式；不要在震颤状态下修改频率或继续运动 | 已确认当前代码无 10000 Hz 配置 |
| A-029 | 真机限位记录器提示没有匹配的 JointState 样本 | 记录器订阅 `/joint_states`，30 秒内没有收到包含 `openarm_right_joint1` 的消息；常见原因是 bringup 已退出、状态广播器未激活或实际关节名称不同 | 先检查 `/joint_states` 的发布者、频率和完整 `name/position`，确认状态链路后再启动记录器 | 待现场检查话题 |
| A-030 | 希望一次记录全部关节的反馈范围 | 当前记录器按一个 `joint` 参数记录；一次记录所有关节的技术上可行，但动作仍须逐关节完成，否则无法归因限位 | 先恢复唯一的真机 bringup 和 `/joint_states` 发布者；当前可逐关节重复记录，批量记录器功能待增加 | 已确认当前无发布者 |
| A-031 | `show_param`/`monitor` 对 can0、can1 的 1–8 号电机全部无响应 | 当前 SocketCAN 是 1 Mbit/s 仲裁、5 Mbit/s FD 数据相位；工具输出不能证明电机内部被改成 10 Mbit/s，也可能是断电、接线、ID 或协议不匹配 | 电机保持禁扭矩，分别对 can0/can1 使用 `discover` 扫描实际波特率和 ID；确认后恢复 1M/5M FD 配置 | 已确认：当前两条总线均无有效电机反馈 |
| A-032 | 震颤的直接原因定位 | `OpenArmHW::on_activate()` 无条件使能并回零，`read()` 未验证电机反馈；`show_param/monitor` 已证明当前无响应，随后 `write()` 仍以 MIT 位置环发送命令 | 先修复电机反馈链路；增加无反馈禁止使能和反馈超时保护，再从低增益逐步恢复控制 | 根因已定位为“无反馈时仍闭环控制”，硬件通信原因待排查 |
| A-033 | 需要现场执行反馈链路排查流程 | 真机 bringup 会使能并回零，不适合第一步排查 | 按“停 ROS→配置 CAN→确认电机供电→monitor→discover→再启动 ROS”的顺序操作 | 流程已补充；待现场执行 |
| A-034 | 怀疑 CAN 端口未关闭导致震颤或无反馈 | `can0/can1` 启动真机时应保持 `UP`；真正需要避免的是旧 ROS/控制节点继续向同一 CAN 总线发送命令 | 配置 CAN 前关闭旧 bringup，使用 `can_configure` 后保持接口 `UP`，只启动一个真机控制栈 | 已澄清；端口状态与进程占用需分别检查 |
| A-035 | 启动真机时未关闭 `teleop_ker.launch.py` | KER 节点会向位置控制器发布命令；真机控制器启动后可能接收到残留或零位目标，引起震颤 | 先停止 KER，再停止/重启真机 bringup；确认只有一个命令发布者后再测试 | 高度可疑；待现场复测 |
| A-036 | KER 节点启动后因 USB `Errno 13 Access denied` 退出 | ROS 映射配置已加载，失败发生在打开 VID 0x303a（PID 0x4002）USB 设备时 | 配置 M5Stack/KER udev 规则并重新插拔设备；不要用 `sudo ros2 launch` 代替权限修复 | 已定位为 USB 权限问题 |
| A-037 | 真机已使能但 KER 不能驱动，用户将状态回显命令理解为控制命令 | `ros2 topic echo /joint_states` 只订阅实时反馈，不发布任何控制；还需确认 KER 输出和位置控制器订阅关系 | 检查 KER 日志、`/openarm_teleop_ker/command`、左右控制器 commands 话题及 controller active 状态 | 待现场检查发布/订阅计数 |
| A-038 | KER 已连接并持续输出 7 关节目标，但真机是否接收仍未确认 | 日志显示 USB 连接成功、streaming started、右/左目标持续发布；这只证明 KER 端正常，不证明控制器订阅或电机反馈正常 | 检查两个 commands 话题的 Publisher/Subscription、控制器 active 状态和 `/joint_states` 是否变化 | KER 端已确认；真机接收链路待验证 |
| A-039 | 控制命令话题只有 KER 发布者，没有控制器订阅者 | `/left_forward_position_controller/commands` 显示 Publisher=1、Subscription=0；右侧话题还未被发现，说明真机位置控制器未正常激活或 ROS 图尚未稳定 | 先停止 KER，单独启动并确认左右 `forward_position_controller` 为 active，再启动 KER | 已定位为控制器接收链路问题 |
| A-040 | 两套真机 bringup 同时运行导致同一 CAN 总线被两个控制环驱动 | `ps` 显示旧 PID 1961961/1962044 与新 PID 2681898/2681922 同时存在；ROS 图也出现重复 controller_manager、硬件和控制器节点 | 立即停止两套 bringup，确认进程和节点各只剩一个，再重新启动；KER 也只能运行一个实例 | 震颤直接原因已确认 |
| A-041 | 需要判断此前对齐方法是否可靠 | 按关节名比较 `/sim/joint_states` 与 `/joint_states` 的思路正确，但此前真机存在无反馈、重复控制栈和 KER 残留，相关数据不能作为验收结论 | 重新按“反馈有效性→映射/零位/方向→软限位→机械端点→相机外参”的顺序验证，每步保留原始时间戳和配置快照 | 新的验收流程已确定 |
| A-042 | 需要自动判断机械端点并同步比较真机/仿真 | 仅凭角度不能证明机械止挡；端点候选应结合目标继续增加、位置平台、速度接近零及力矩/电流上升，最终仍需人工确认 | 记录命令、仿真角、真机角、误差、速度、力矩和端点候选；按小步扫描→软限位→单关节端点的渐进流程执行 | 方案已确定；现有监视器可先记录角度和误差 |
| A-043 | 需要明确先启动仿真还是真机 | 真机当前曾出现无反馈和震颤，仿真可先验证记录器和模型范围；两端最终需同时运行才能做同步误差比较 | 先单独验证 MuJoCo，再在电机反馈有效且无重复控制栈后启动真机，最后启动只读对齐监视器和单一控制源 | 启动顺序已确定 |
| A-044 | Dora KER 节点在 `_ping_and_fetch_schema` 超时并退出 | 2026-09-10 烟测中已复现：设备打开后返回空 buffer，没有 schema；常见原因是 KER Manager/`openarm-ker-cli stream`/旧 Dora 占用或 KER 未重新枚举 | 关闭所有 KER 访问进程，拔插设备并确认 udev 权限，先做独立 KER 测试，再启动 MuJoCo dataflow | 已确认 KER 握手失败，待清理 USB 占用并复测 |
| A-045 | `smoke_collect.py` 启动前 `AssertionError` | dataflow 新增 `ros2-joint-state-bridge` 后，烟测脚本仍按旧的五节点集合做精确断言 | 将烟测校验改为检查包含桥接节点的必需节点子集 | 已修复，需重新运行烟测 |
| A-046 | MuJoCo 左臂无法运动 | `--enable-collision` 启用 demo 场景中的黑色盒子碰撞体，左臂初始运动路径与其发生碰撞 | 保留碰撞保护，定位黑盒对应的 geom/body，调整场景物体或初始姿态；仅用关闭碰撞做诊断 | 已确认关闭碰撞后左臂恢复，待调整场景 |
| A-047 | KER 连接成功后连续出现 encoder errors | 日志显示固件 `3.3.0`、硬件 `3.0.0` 已读取；`flags=[False, True, True, True, True, True, True, True, False, True, True, True, True, True, True, True]`，只有通道 0、8 正常，其余 14 通道持续报错，5 秒后保护退出 | 保持保护退出逻辑，检查 KER 供电、传感器/校准、线束、USB 独占和固件状态；不要用 MuJoCo collision 设置掩盖错误 | 已确认与 collision 无关，待现场检查 KER 通道 |

后续新问题按 A-009 起编号。解决后保留问题行，补充修改文件、验证方法与实际结果；若只有推测或尚未执行，明确写“待验证”。

## 遥操臂同时控制真机与仿真、同时采集的方案

KER USB 由一个读取进程持有，在软件中分发数据，不同时启动 ROS KER 节点和 Dora KER 节点争用设备。拟议结构：

```text
KER → 单一读取节点 → 解绕、单位换算、映射 → 统一目标（时间戳、序号）
                                         ├→ 真机控制适配器 → 真机
                                         ├→ 仿真控制适配器 → MuJoCo
                                         └→ 记录器：公共目标
真机反馈、真实相机 ─────────────────────────→ 记录器：real
仿真反馈、虚拟相机 ─────────────────────────→ 记录器：sim
```

每个适配器仍需要自身的限位、速度和失联处理；应同时记录公共目标与各端最终下发命令，以识别限幅等因素造成的差异。上述双端桥接尚未实现或验证，当前已有链路是单独的 MuJoCo 采集。

“相同角度”先定义为同一关节坐标下的相同目标 q；真正到达的角度由两端反馈分别验证，不能把目标复制为观测。“相同末端位置”还需要统一基座/任务坐标系、末端定义与运动学，并考虑 IK 解和碰撞限制；第一阶段优先做关节目标对照。

同步采集不要求两个程序直接连接 KER。记录公共动作、真机状态、仿真状态与各自图像，保留来源和采样时间，使用统一或已标定关系的时钟，明确仿真时间与现实时间映射。之后按时间对齐并检查延迟、丢帧和跟踪误差。当前 Dora 记录器的单组 action/observation schema 不能直接当成 real/sim 双组记录器使用，需要扩展或增加独立记录通道。

### 已有 KER → MuJoCo 入口

```bash
cd /home/tangyuan/openarm_ws/dora/dora-openarm-data-collection
bash local/run_ker_mujoco.sh
```

已有流程不包含真机从臂控制节点。入口打开 MuJoCo 窗口，采集 UI 为 `http://localhost:8000`。只有在网页开始录制后才采集 episode；正式任务成功才标记成功，连通性测试标记失败。仿真从启动起即接收遥操目标，与录制按钮分开。

运行前确认没有其他 KER USB 读取进程。模型显示中的 RViz GUI 不读取 KER，可以共存，但不会自动跟随 Dora/MuJoCo；若要在 RViz 显示仿真实际状态，还需要将 MuJoCo 反馈桥接为 ROS JointState，并替换 GUI 状态源。

映射使用 `local/ker_mapping.yaml` 快照，源 ROS YAML 的修改不会自动同步。每次启动使用独立输出目录并保存配置，保留动作和观测原始时间戳；不能把配置频率当作实测同步频率。

参考：[现有 MuJoCo 启动和采集说明](../dora/dora-openarm-data-collection/local/README_KER_MUJOCO.md)。该说明包含先前的链路验证记录，不等于本轮逐关节验证结果。

## MuJoCo / 真机只读对齐监视器

已新增 `src/openarm_alignment`：MuJoCo 数据流通过 Dora ROS bridge 发布 `/sim/joint_states`，监视器订阅该话题和真机 `/joint_states`，写入逐样本 CSV 及退出汇总 CSV。它不创建任何控制发布器，因此不能使能、回零或移动真机。

详细启动和逐关节方向、限位验证方式见：[监视器说明](../src/openarm_alignment/README.md)。方向字段 `same` 和 `opposite` 只在两端均有足够幅度变化时判断；限位对比只基于记录的状态与 URDF 参考范围，不能代替真机安全保护或授权的机械端点测试。

## 当前下一步

### A-052：右 J1 正向稳定段结果

在目标 `+0.15 rad` 保持阶段截取最后 2 秒，得到 21 个样本：平均误差 `-0.000921 rad`（`-0.0528°`），RMSE `0.000941 rad`（`0.0539°`），最大绝对误差 `0.001148 rad`（`0.0657°`），标准差 `0.000190 rad`。该正向静态窗口表现良好，暂不需要修改右 J1 的零位或比例映射。仍需完成负向稳定段，以检查方向和回差。

### A-053：左右双臂静止 5 秒统一采集脚本

新增只读脚本 `alignment/capture_static_gap.py`。脚本等待 `/sim/joint_states` 和 `/joint_states` 同时出现，然后连续采集 5 秒，按关节名匹配左右臂和夹爪，自动输出逐样本文件及汇总文件。脚本不发布控制命令，也不调用控制器服务。

```bash
cd ~/openarm_ws
source /opt/ros/jazzy/setup.bash
source ~/openarm_ws/install/setup.bash
python3 alignment/capture_static_gap.py \
  --duration 5 \
  --output alignment/results/right_left_static_gap
```

输出：

```text
alignment/results/right_left_static_gap_samples.csv
alignment/results/right_left_static_gap_summary.csv
```

采集前先将真机保持在安全静止姿态，并确认仿真和真机都已启动、只有一个控制栈和一个 bridge。汇总中的 `mean_error_rad`、`rmse_rad` 和 `max_abs_error_rad` 是这 5 秒静止窗口的结果；若两路消息不同步或关节名不完整，先排查消息链路，不把缺失数据当作零误差。

### A-048：终端提示 `Package 'openarm_alignment' not found`

原因是终端只 source 了 `/opt/ros/jazzy/setup.bash`，没有加载工作区 overlay。当前包已安装在 `~/openarm_ws/install/openarm_alignment`，每个新终端都必须先加载 ROS，再加载工作区：

```bash
cd ~/openarm_ws
source /opt/ros/jazzy/setup.bash
source ~/openarm_ws/install/setup.bash
ros2 pkg prefix openarm_alignment
```

若仍找不到包，重新构建并重新加载：

```bash
cd ~/openarm_ws
colcon build --packages-select openarm_alignment --symlink-install
source install/setup.bash
```

验证成功后再启动监测器。不要在未 source 工作区的终端直接运行 `ros2 launch openarm_alignment ...`。

### A-049：监测器启动后真机没有动作

对齐监测器是只读节点，不会向真机发送控制命令；监测器启动后真机无动作通常不是监测器故障。按以下顺序检查：

```bash
ros2 control list_controllers
ros2 topic info /right_forward_position_controller/commands --verbose
ros2 topic echo /joint_states --once
ip link show can0
ip link show can1
```

右侧位置控制器必须为 `active`，commands 话题必须有控制器订阅者，`/joint_states` 必须持续变化且 CAN 接口为 `UP`。若只启动监测器而没有重新发布目标，真机保持原位置是正常现象。发布测试命令前确认没有重复 bringup、重复 bridge 或 KER 节点。

### A-050：右 J1 静态/动态检测文件的初步查看

`right_joint1_static_summary.csv` 和 `right_joint1_dynamic_summary.csv` 已生成，但监视器会记录完整双臂 JointState；文件名中的 static/dynamic 只是输出文件名，不会自动筛选稳定窗口。当前两个文件中右 J1 都仍包含约 `±0.2 rad` 的运动范围，且最大误差约 `0.17～0.18 rad`，因此不能直接当作“停止 5 秒后的静态结果”。正式静态结论必须按时间窗口截取每次目标保持的最后 2 秒后重新计算。

### A-061：左右两侧静态偏差整理与修改原则

当前 5 秒静态基线中，右侧较大的固定偏差是右 J2/J6 约 `0.33°`、右夹爪约 `1.43°`；左侧较大的固定偏差是左 J5 `0.666°`、左 J6 `0.935°`、左 J7 `0.738°`、左夹爪 `0.829°`。这些数值表示 `real - sim` 的当前姿态偏差，先作为校准候选，不能直接写入真机反馈。

修改顺序：

1. 在同一姿态重复静止采集至少两次，确认偏差均值和符号稳定。
2. 对候选关节分别执行 `+0.15 rad`、`-0.15 rad` 保持测试，排除动态延迟和回差。
3. 若正负方向稳定偏差相近，优先修改对应 ROS 映射的 additive offset：`q_corrected = q_raw - mean_error`。本工程映射字段位于 `src/openarm_teleop_ker/config/ker_mapping.yaml` 的 `offset_angles` 或关节映射 `offset`，具体以实际控制链路为准。
4. 若误差随角度幅值变化，检查比例系数/减速比：`q_corrected = scale * q_raw + offset`，不要只加 offset。
5. 若正负方向符号相反，先检查方向符号和左右镜像映射，不要用 offset 掩盖取反错误。
6. 每次只改一个关节，保存配置快照，重启唯一控制栈后重新做 5 秒静态和正负保持验证。

建议暂不修改的阈值：静态 RMSE 小于约 `0.003 rad`（`0.17°`）先保留原配置；超过该值且重复测试稳定，再进入校准。夹爪单独处理，因为其从动关节和零位定义不同。

### A-062：左 J5 单关节校准计划

左 J5 当前静态 gap 约 `0.01162 rad`（`0.666°`）。相对于本记录建议的 `0.003 rad`（`0.17°`）静态阈值，这属于需要复核的明显偏差，但还不能仅凭一次静止姿态直接写入配置。

本次只测试左 J5：安全姿态保持后，发送 `+0.15 rad` 并保持 5 秒，再回零；随后发送 `-0.15 rad` 并保持 5 秒，再回零。正负保持段都稳定且偏差符号一致后，才对左 J5 单独计算 offset。校准对象应是真机侧的零位/反馈映射，使真机反馈与公共关节坐标一致；不要修改 MuJoCo 模型参数来掩盖真机误差。MuJoCo 只在确认模型坐标定义错误时才修改。

### A-063：左 J5 正负运动测试结果

`left_joint5_static_pos_summary.csv` 实际包含左 J5 的 `±0.15 rad` 运动过程，不是静止窗口。全段 RMSE 为 `0.02114 rad`（`1.21°`），最大误差 `0.14172 rad`（`8.12°`），因此不能直接用全段 RMSE 做校准。按仿真角度筛选并取正、负目标各自最后 2 秒后：正向平均误差约 `-0.01655 rad`（`-0.947°`），负向平均误差约 `+0.00780 rad`（`+0.447°`）。正负偏差不相等，表现出回差或动态跟踪影响，当前禁止直接写入单一 offset；应先用更慢的目标变化和独立稳定窗口复测。

### A-064：左 J5 正确稳定段复测步骤

正向和负向必须分别建立监测文件。启动监测器后立即发布一个目标，目标保持 5 秒；在目标仍保持时停止监测器，再停止命令发布，最后回零。不要让监测器跨越回零过程。只对左 J5 行取最后 2 秒计算均值、RMSE、标准差和最大误差。正向完成后，回到安全姿态，再重复负向测试。

### A-065：左 J5 清洁复测文件状态

已生成 `left_j5_pos_clean.csv` 和 `left_j5_pos_clean_summary.csv`；正向汇总全段 RMSE 为 `0.02631 rad`，仍包含到位过程。按仿真角度大于 `0.1 rad` 并取最后 2 秒筛选后，38 个样本的平均误差约 `-0.01568 rad`、RMSE `0.01749 rad`、最大误差 `0.03139 rad`，说明真机在正向目标保持时仍未完全贴合仿真。`left_j5_neg_clean.csv` 原始文件已存在，但对应 summary 尚未生成，需要从原始文件计算或重新执行负向监测。

### A-066：左 J5 负向汇总结果

`left_j5_neg_clean_summary.csv` 已生成。左 J5 负向全段 RMSE 为 `0.01538 rad`（约 `0.881°`），最大误差 `0.14370 rad`（约 `8.23°`），仿真范围 `-0.15～0 rad`，真机范围 `-0.142～0.0147 rad`。筛选负向目标最后 2 秒仍只有 19 个样本且 RMSE `0.06498 rad`，说明负向保持段未稳定，当前不能用该结果校准 offset，必须重新采集完整负向稳定窗口。

### A-067：左 J5 最新负向数据仍混入回零

最新负向文件的最后样本中，仿真仍为约 `-0.15 rad`，但真机从约 `-0.142 rad` 跳回 `-0.008～-0.006 rad`，造成 `0.14 rad` 左右的峰值误差。这表明停止发布器或回零动作发生在停止监测器之前，最后窗口不是稳定保持段。正负方向均未满足单一 offset 的校准条件，必须再次测试并严格先停监测器、再停发布器、最后回零。

### A-068：左 J5 新一轮负向测试文件

新一轮负向测试使用 `left_j5_neg_clean2` 文件名，避免覆盖旧数据。目标保持 5 秒后必须先停止监测器，再停止发布器，最后回零。

### A-069：左 J5 `neg_clean2` 仍不是稳定窗口

该汇总全段 RMSE 为 `0.01429 rad`，最大误差 `0.12692 rad`。原始数据最后几帧中仿真仍保持 `-0.15 rad`，而真机从 `-0.142 rad` 快速回到约 `-0.023 rad`，说明发布器停止后真机控制器的命令超时/回零过程被记录进文件。该文件不能用于计算负向静态 offset。必须让发布器持续运行到监测器已经停止，再停止发布器。

### A-070：左 J5 `neg_clean3` 负向 offset（暂定）

`neg_clean3` 的汇总全段 RMSE 为 `0.00739 rad`，最大误差 `0.04017 rad`。负向目标最后 2 秒筛选到 40 个样本，误差均值 `+0.00707 rad`，中位数 `+0.008281 rad`，RMSE `0.01035 rad`；大多数样本稳定在 `+0.008281 rad`，末尾有一个异常点。因此左 J5 负向校准值可暂定为 `-0.008281 rad`（约 `-0.474°`）作用于真机侧反馈映射，但必须用重新采集的正向稳定窗口确认后才能正式写入配置。

### A-071：左 J5 正负校准值保存位置

左 J5 正向稳定段测得 `real-sim=-0.015681 rad`，对应真机反馈修正量 `+0.015681 rad`；负向稳定段中位数测得 `real-sim=+0.008281 rad`，对应修正量 `-0.008281 rad`。两者不一致，说明当前存在方向相关回差或残余动态误差，不能写入 `ker_mapping.yaml` 的单一 `offset_angles.left_arm[4]`。两组暂定值已保存到 [left_j5_calibration.yaml](left_j5_calibration.yaml)，仅作校准记录，不会被运行时自动加载。正式修改前必须复测到正负修正量一致。

### A-072：offset 基准与导入层级

需要区分三种目的：

- **测量真实 gap**：保留仿真和真机原始反馈，不应用 offset，否则会把误差隐藏。
- **统一关节坐标用于比较**：通常把真机编码器反馈转换到公共关节坐标，再比较仿真；可以在真机侧反馈适配器或监视器中应用 `q_real_corrected = q_real - e`，不写电机 EEPROM。
- **修正 MuJoCo 模型零位**：如果确认真实机械零位是基准、而 URDF/MuJoCo 零位定义错误，则修改 MuJoCo/URDF 的 joint origin 或比较变换；这不会修复真机控制误差。

左 J5 当前正负 offset 不一致，不能导入真机控制链路。`ker_mapping.yaml` 的 `offset_angles` 是 KER 命令映射，不是真机反馈校准入口；修改它会改变发送给控制器的目标，可能造成真实运动。正式导入前必须先确定公共坐标基准、完成正负稳定复测，并在仿真或离线回放中验证。若只想验证效果，应先在监视器/离线分析中应用临时 offset，确认结果后再实现真机反馈适配器。

### A-073：左 J5 MuJoCo 侧候选修正

按真机为物理参考，使用正负稳定误差的中心值 `(-0.015681 + 0.008281) / 2 = -0.003700 rad`，得到候选变换 `sim_corrected = sim_raw - 0.003700 rad`（约 `-0.212°`）。该值已保存到 [mujoco_calibration.yaml](mujoco_calibration.yaml)，状态为 `comparison_only`，当前不会自动改变 MuJoCo 物理模型或运行时输出。应用前必须确认接受方向相关残差约 `±0.012 rad`，或先解决回差后再把该值写入仿真映射。

### A-074：监视器支持 MuJoCo 侧比较变换

对齐监视器新增 `sim_offsets` 参数，只在比较和 CSV 输出中计算 `sim_corrected = sim_raw + offset`，不改变 MuJoCo 物理状态，也不改变真机命令。使用示例：

```bash
ros2 launch openarm_alignment alignment_monitor.launch.py \
  sim_offsets:='{"openarm_left_joint5": -0.0037000192045282855}' \
  csv_path:=alignment/results/left_j5_sim_corrected.csv \
  summary_path:=alignment/results/left_j5_sim_corrected_summary.csv
```

该功能用于重新采集并比较校准前后的 gap；确认残差下降后，才考虑修改 MuJoCo/URDF 的正式零位或映射。

### A-075：`sim_offsets` 被 launch 解析为字典

ROS launch 会把 JSON 文本自动解析为字典，而节点参数要求字符串，导致启动失败。已在 launch 文件中用 `ParameterValue(..., value_type=str)` 强制保持字符串，并重新构建 `openarm_alignment`。原来的 `sim_offsets:='{"openarm_left_joint5": -0.0037000192045282855}'` 命令可继续使用。

### A-076：应用 MuJoCo 候选 offset 后的复测不能判定有效性

`left_j5_sim_corrected_pos_summary.csv` 和 `left_j5_sim_corrected_neg_summary.csv` 仍包含启动/停止瞬态；正向和负向稳定筛选分别只有 24、21 个样本，且真机在窗口内明显离开目标位置。修正后的 RMSE 不能与原始稳定段比较，当前不能据此判断 `-0.003700 rad` 是否有效。必须按 A-069 的停止顺序重新采集，并确认保持窗口内真机角度稳定后再比较校准前后 RMSE。

### A-077：清空左 J5 修正复测文件

已清空以下四个文件内容，保留文件名以便监测器重新写入：

```text
alignment/results/left_j5_sim_corrected_pos.csv
alignment/results/left_j5_sim_corrected_pos_summary.csv
alignment/results/left_j5_sim_corrected_neg.csv
alignment/results/left_j5_sim_corrected_neg_summary.csv
```

历史 `gap_all_*`、`sim_real_*`、`left_joint5_static_pos_*` 等文件未删除。

### A-078：修正后正负文件仍包含停止瞬态

最新 `left_j5_sim_corrected_pos/neg_summary.csv` 的方向样本均为 0，且仿真范围包含 `0 rad`、真机范围回到接近 `0 rad`，说明监测器仍覆盖了回零阶段。不能用这两份 summary 判断 MuJoCo offset。为避免人工 Ctrl+C 顺序错误，下一轮可先启动并保持目标发布，再用 `timeout` 让监测器自动结束；监测器结束后再停止发布器。

### A-079：CSV 文件名被当作命令执行

`left_j5_sim_corrected_neg2.csv` 是数据文件，不是可执行命令。使用 `ls`、`grep` 或 `column` 查看内容。该轮负向文件和 summary 已实际生成。

### A-080：左 J5 修正后负向稳定段结果

`left_j5_sim_corrected_neg2_summary.csv` 的左 J5 行只有 34 个稳定样本，仿真修正后范围约 `-0.1534 rad`，真机约 `-0.1417 rad`，平均误差 `+0.01175 rad`、RMSE `0.01185 rad`（约 `0.679°`）。相比原始负向稳定误差约 `+0.00828 rad`，使用中心值 `sim_offset=-0.003700 rad` 使负向误差增加，说明单一中心 offset 不能同时补偿正负方向；当前仍不应写入正式 MuJoCo/URDF。

### A-081：方向回差的处理方案

左 J5 正向和负向稳定误差符号相反，不能用一个常数 offset 解决。先区分原因：

- 若目标停止后真机角度仍继续变化，属于控制延迟或命令超时，应降低目标变化速度、提高保持时间并校准时间对齐。
- 若从正向接近同一角度和从负向接近同一角度，真机最终位置仍不同，且速度已接近零，属于机械回差、减速器间隙或静摩擦。

推荐按同一目标角度做“正向接近→保持 5 秒→回到远处→负向接近→保持 5 秒”的重复测试，至少三轮。记录两次稳定位置的差值 `backlash = q_positive - q_negative`，不要把它当作零位 offset。

解决顺序：检查联轴器、减速器、轴承和紧固件；确认控制器位置/速度增益与命令超时设置；再在真机侧适配器增加方向相关补偿或死区补偿。补偿应只作用于真机反馈或真机命令映射，保留原始反馈用于验收。MuJoCo 可以增加等效的静摩擦/回差模型用于动力学仿真，但不应通过改变 joint origin 隐藏真实机械间隙。

在回差未测定前，不写入单一 MuJoCo offset，也不修改电机零位参数。验收标准应同时报告正向误差、负向误差和回差宽度。

### A-082：第一步只检查左 J5 控制延迟

第一步不修改配置，只做单方向阶跃测试。让左 J5 从当前安全姿态移动到 `+0.05 rad`，保持至少 5 秒并持续记录；观察真机是否在保持阶段继续变化。若仿真已稳定而真机仍明显变化，优先排查控制延迟或命令超时；若两端都稳定但位置固定不同，再进入机械回差测试。

### A-056：右臂及双臂静止 5 秒统一采集结果

`right_left_static_gap_summary.csv` 共记录每个关节 250 个样本，标准差接近 0，说明这 5 秒窗口内状态稳定。右臂静态差异为：J1 `0.000878 rad`（`0.050°`）、J2 `0.006044 rad`（`0.346°`）、J3 `0.000572 rad`（`0.033°`）、J4 `0.002102 rad`（`0.120°`）、J5 `0.001301 rad`（`0.075°`）、J6 `0.005791 rad`（`0.332°`）、J7 `0.001749 rad`（`0.100°`）。右夹爪为 `0.024978 rad`（`1.431°`）。

当前姿态下 J1、J3、J4、J5、J7 的静态 gap 较小；J2、J6 有约 `0.33°` 的固定偏差；右夹爪存在约 `1.43°` 的固定偏差。该结果只代表当前静止姿态，不能替代各关节正负角度保持测试，也不能直接证明动态跟踪误差。

### A-057：左臂 gap 测试计划

右臂 5 秒静态基线已保存。左臂按相同方法逐关节测试，先测左 J1，再测 J2～J7，最后测左夹爪。每个关节使用独立输出文件，并只统计目标保持阶段最后 2 秒；测试期间其他关节保持当前安全姿态。

### A-058：左臂测试文件状态

当前结果目录中只发现 `left_joint1_static_pos.csv` 及其汇总文件；该文件包含全部关节的运动记录，左 J1 行的 RMSE 为 `0.00593 rad`、最大误差 `0.10884 rad`，方向样本仅 3/3，不能作为稳定静态 gap。之前的 `right_left_static_gap_summary.csv` 是统一静止姿态基线，不能替代左臂各关节的正负目标保持测试。左 J2～J7 和左夹爪需要按 A-057 分别保存独立稳定窗口后再下结论。

### A-059：重新采集左臂全部关节 gap

采集脚本增加了 `--joint-prefix` 参数。使用 `openarm_left_` 时，只保存左 J1～J7 和左夹爪，避免右臂数据混入：

```bash
/usr/bin/python3 alignment/capture_static_gap.py \
  --duration 5 \
  --joint-prefix openarm_left_ \
  --output alignment/results/left_arm_static_gap
```

输出为 `left_arm_static_gap_samples.csv` 和 `left_arm_static_gap_summary.csv`。采集期间左臂保持安全静止姿态；该文件是统一静态基线，随后仍需对左臂各关节做正负目标保持测试。

### A-060：左臂 5 秒静态采集结果

`left_arm_static_gap_summary.csv` 已生成，每个左臂关节有 251 个样本，5 秒窗口内标准差很小。静态 RMSE（弧度/角度）为：左 J1 `0.002457 / 0.141°`，左 J2 `0.002615 / 0.150°`，左 J3 `0.002098 / 0.120°`，左 J4 `0.001274 / 0.073°`，左 J5 `0.011622 / 0.666°`，左 J6 `0.016324 / 0.935°`，左 J7 `0.012874 / 0.738°`，左夹爪 `0.014469 / 0.829°`。当前左 J1～J4 静态偏差较小，左 J5～J7 和左夹爪偏差较大，需进一步做目标保持和映射检查。

### A-054：`rclpy._rclpy_pybind11` 导入失败

ROS 2 Jazzy 的 `rclpy` 使用系统 Python 3.12 编译；若终端处于 Miniconda Python 3.13 环境，会出现 `ModuleNotFoundError`。采集脚本必须使用系统解释器：

```bash
/usr/bin/python3 --version
/usr/bin/python3 alignment/capture_static_gap.py \
  --duration 5 \
  --output alignment/results/right_left_static_gap
```

不要用指向 `~/miniconda3/bin/python` 的 `python3` 运行该脚本。

### A-055：静态采集脚本在日志回调处退出

脚本原先使用了 `logger.info("... %s", value)` 的 Python logging 写法，但 ROS 2 Jazzy 的 `RcutilsLogger.info()` 只接受一个字符串参数，导致定时器回调抛出 `TypeError`。已改为 f-string；输出文件写入逻辑不变。

## 2026-09-10 仿真与真机 gap 初测记录

本次监控生成了以下文件：

- `alignment/results/sim_real_samples.csv`：逐周期、逐关节原始比较数据。
- `alignment/results/sim_real_summary.csv`：当前一次测试的汇总（每关节 472 个样本）。
- `alignment/results/gap_all_samples.csv`：包含多次动作的原始比较数据。
- `alignment/results/gap_all_summary.csv`：多次动作的汇总（每关节 15207 个样本）。

初测确认仿真和真机都能响应同一条 ROS 目标命令，方向一致，存在角度差异。`sim_real_summary.csv` 中固定差异较明显的关节包括右 J1 `0.01018 rad`、右 J5 `0.01545 rad`、左 J3 `0.01507 rad`、左 J7 `0.01358 rad`、右夹爪 `0.02536 rad`。这些数值主要来自当前姿态/零位比较，不能直接当作最终标定偏置。

监控期间出现 `Waiting for fresh complete simulation and real JointState messages`，表示某一时刻没有同时收到新鲜状态；退出时仍成功写出 summary。`gap_all_summary.csv` 中较大的 `max_abs_error_rad` 可能包含运动启停瞬态和两端异步采样，因此正式 gap 应按单关节的稳定保持段计算。

### 逐关节 gap 测试协议

每次只测试一个关节，仿真和真机同时运行，对同一个 ROS 命令话题发送同一目标：

```text
当前安全姿态 → +0.15 rad（保持 2 s）→ 当前安全姿态
当前安全姿态 → -0.15 rad（保持 2 s）→ 当前安全姿态
```

记录每个保持段的仿真角度、真机角度、误差均值、误差标准差、最大误差和方向；丢弃运动开始/停止的瞬态。J1～J7 完成后，再单独测试夹爪。未经安全批准不执行机械硬端点动作，限位先使用软件范围内侧值。

单关节结果命名建议：

```text
alignment/results/right_j1_gap.csv
alignment/results/right_j1_gap_summary.csv
alignment/results/left_j1_gap.csv
alignment/results/left_j1_gap_summary.csv
```

验收字段：`direction` 不得出现 `opposite`；稳定段误差用于零位/比例判断；`sim_min/max_rad` 与 `real_min/max_rad` 用于范围比较。完成一个关节后，将结论和对应文件追加到本记录。

### 动态误差的处理与修正

动态误差不能直接通过把 CSV 中的最大误差减掉来修正。先区分三类原因：

1. **采样不同步或通信延迟**：仿真和真机时间戳不同，启动、停止、换向时会出现暂时性大误差。应先记录两端时间戳，估计延迟，再用时间偏移对齐后计算误差。
2. **真机跟踪滞后**：目标改变后，真机尚未到位而仿真已经到位。应降低命令变化速度、延长保持时间，并用到位后的稳定窗口评价；不能用启动瞬间的误差作为零位偏置。
3. **静态映射误差**：稳定后仍持续存在的固定偏差，才考虑零位偏置、方向符号或比例系数修正。

修正顺序固定为：

```text
先清理重复控制节点和重复 bridge
→ 校准仿真/真机时间对齐
→ 用稳定保持段测量动态误差
→ 检查零位偏置
→ 检查方向符号
→ 检查角度比例/减速比
→ 重新执行正负方向验证
```

不要为了让曲线重合而直接修改真机反馈。任何映射修改都应先写入独立配置快照，并同时保留原始 `/sim/joint_states`、`/joint_states` 和控制命令数据。

右 J2 的阶段性结论：早先静止测试 RMSE 约 `0.00158 rad`（约 `0.09°`），说明零位附近静态偏差较小；本次运动测试 RMSE `0.0240 rad`、最大误差 `0.2071 rad`，说明运动过程仍有延迟或不同步。当前标记为“静态基本准确，动态 gap 待稳定段复核”，不能直接修改 J2 零位。

正式复测时，每个目标角度至少保持 3 秒，舍弃前 1～2 秒，只统计最后 1 秒；正向、负向和回零分别保存窗口。只有稳定窗口仍有持续偏差，才进入映射参数修正。

### 右臂重新采集：静态数据与动态数据

本轮从右臂开始。静态数据和动态数据必须分开保存、分开评价，不能混在同一个 RMSE 中。

**静态数据流程**：每次只移动一个关节，目标角度到达后保持 5 秒；前 3 秒视为到位过程，最后 2 秒作为静态窗口。每个关节至少采集零位、正向 `+0.15 rad`、负向 `-0.15 rad` 三个状态，并在每个状态之间回到安全姿态。静态窗口计算均值、标准差、RMSE 和最大绝对误差。

**动态数据流程**：记录从目标改变前开始，到真机和仿真回到安全姿态结束的完整时间序列，不丢弃启动、加速、减速和换向样本。动态数据用于测量响应延迟、上升时间、峰值误差、稳态时间和是否出现超调；它不用于直接计算零位偏置。

推荐的单关节动态序列为：

```text
安全姿态保持 2 s
→ +0.15 rad，保持 5 s
→ 回到安全姿态，保持 2 s
→ -0.15 rad，保持 5 s
→ 回到安全姿态，保持 2 s
```

静态文件和动态文件分别命名，例如：

```text
alignment/results/right_joint1_static.csv
alignment/results/right_joint1_static_summary.csv
alignment/results/right_joint1_dynamic.csv
alignment/results/right_joint1_dynamic_summary.csv
```

动态数据分析至少报告：命令改变到仿真响应的延迟、命令改变到真机响应的延迟、两端延迟差、峰值误差、达到稳定窗口所需时间，以及稳定后的静态误差。所有动态测试仍使用小角度和软件限位；出现异响、抖动或跟踪失控时立即回零并停止测试。

### 先做 MuJoCo 限位扫描

遥操臂很难保证只动一个关节时，不要用 KER 做第一轮限位测试。MuJoCo 的独立扫描脚本会直接读取模型的关节 `range`，在下限、中点和上限执行 `mj_forward`，不启动控制器、不接真机、不移动实体：

```bash
cd /home/tangyuan/openarm_ws
source dora/dora-openarm-data-collection/.venv/bin/activate
python alignment/check_mujoco_limits.py
```

结果写入 `alignment/results/mujoco_limit_scan.csv`。已从仓库中的 V2 joint limits 和 pinch-gripper joint limits 补入 `alignment/mechanical_limits.csv`，但这些行的 `source_type=project_config` 表示设计/软件参考，不是机械端点实测，因此扫描结果会显示 `REFERENCE_ONLY`。只有将某行改为经过确认的 `source_type=measured_mechanical`，该行才会在范围包含时显示 `PASS`；范围超出时显示 `FAIL`。限位数值统一用弧度。

扫描验证的是模型边界和数值运动学可达性，不等于碰撞安全或驱动器硬限位。模型范围在机械范围内才可判为范围一致；模型比机械范围大时必须先收紧模型或控制器范围。确认无误后，再用 KER 做小幅动态方向测试。

1. 现场确认真机版本、夹爪型号、左右臂及 CAN 对应关系。
2. 从 `openarm_right_joint1` 开始，在模型中设为 0，记录连杆朝向；小幅增加角度，观察旋转轴和正方向。
3. 对照实体结构填写关节对应关系、零位与方向；依次完成右臂 J1～J7、左臂及夹爪。不通过触碰机械端点完成首次限位核对。
4. 明确并实现真实反馈只读入口，再检查实际测量值与 RViz 姿态是否一致。
5. 核对机械及电机范围，解释配置差异，确定软件工作范围；如需修改，同步 URDF、仿真及相关控制配置并验证。
6. 使用多个已知姿态复核，而不只验证零位；记录角度误差、连续性及反馈有效性。验收阈值根据实际设备和任务要求确定。
7. 关节对齐后单独建立相机标定表：设备与分辨率、内参及畸变模型、外参父子坐标系和变换方向、标定方法、误差与日期。固定相机核对基座关系，腕部相机核对末端安装关系；数据采集前验证图像与关节时间同步。

阶段验收目标：反馈来源明确、关节对应正确、方向和零位正确、角度连续、限位差异均有解释。RViz 姿态一致不等于动力学或相机标定已完成。

## 关键文件

- [CSV 对照表](joint_alignment_checklist.csv)
- [展开 URDF 快照](openarm_v20_reference.urdf)
- [V2 关节限位源配置](../src/openarm_description/assets/robot/openarm_v2.0/config/arm/joint/joint_limits.yaml)
- [KER 映射及限位](../src/openarm_teleop_ker/config/ker_mapping.yaml)
- [硬件插件源码](../src/openarm_ros2/openarm_hardware/src/openarm_simple_hardware.cpp)
- [历史 J7 回绕修复说明](../wjz-log/joint7_angle_wrap_fix.md)

## 更新记录

- 2026-09-09：创建本记录；整理 RViz 启动状态、关节对照表字段、消息链路、已发现问题及后续顺序。记录模型快照与 CSV，未修改真机配置，未进行真机对齐验收。
- 2026-09-09：补充关节对应、零位、正方向的双侧核对方法；明确当前 GUI 只能验证模型定义，真机反馈和电机 ID 的动态对应仍待验证。
- 2026-09-09：检查现有 KER → MuJoCo 数据流，补充单一 USB 读取、多端目标分发、双端反馈采集的方案；双端控制和同步记录尚未实现。
- 2026-09-09 17:01：启动已有 KER → MuJoCo 流程；日志确认 USB、五路相机及事件循环初始化完成。没有启动真机控制或测试录制；逐关节运动效果待人工确认。
- 2026-09-09：新增 MuJoCo 到 ROS 的 JointState bridge 和只读对齐监视器；监视器的离线逻辑测试与 ROS 包构建通过。尚未同时接收真实真机和 MuJoCo 状态，未得到实际对齐结论。
- 2026-09-09：发现 MuJoCo 启动脚本必须加载 ROS 环境，并修正其 `set -u` 与 ROS 环境脚本的兼容问题。先前会话的启动器和孤立 Dora 子进程已按 PID 精确结束，锁已确认释放。
- 2026-09-09：修正新增 bridge 的 Dora 预构建流程；完整 dataflow 构建成功，并用 `--stop-after 8s` 验证 bridge、MuJoCo、KER、录制器和 UI 全部就绪且正常退出。
- 2026-09-09：补充单关节采集操作：先检查两个 JointState 源，再逐关节小幅正反向运动，结合误差、方向和观测范围判断；明确当前 KER→MuJoCo 不会自动控制真机。
- 2026-09-09：新增 `alignment/check_mujoco_limits.py` 和机械限位模板；已从当前 MuJoCo demo 模型扫描 18 个 hinge 关节并生成 `alignment/results/mujoco_limit_scan.csv`。随后从 V2 arm 和 pinch-gripper 配置补入参考值；结果为 `REFERENCE_ONLY`，不代表机械端点已实测。
- 2026-09-09：搜索未发现完整真机机械端点数据；新增 `alignment/start_real_openarm.sh` 和 `openarm_real_limit_recorder`，构建通过、反馈记录器测试通过。未启动真机或执行端点运动。
- 2026-09-09：补充说明 `--oncece` 拼写错误，以及记录器选择一个关节并不等于控制系统只移动一个关节；关节限位测试仍需逐关节隔离动作。
- 2026-09-09：为真机 bringup 增加 `use_rviz` 开关，并让真机脚本关闭 RViz；`openarm_bringup` 构建和 launch Python 语法检查通过。
- 2026-09-09：核对真机启动 README 与脚本；明确 launch 参数不能作为独立 Bash 命令逐行执行。用户本次输入未启动真机。
- 2026-09-10：修复烟测节点断言后重新运行；节点校验通过，但 KER `leader` 仍因 schema 空响应退出，MuJoCo 随后被停止。当前尚未生成有效验证 episode。
- 2026-09-10：检查左 J5 新一轮 `left_j5_delay_test` 阶跃数据。全程摘要的 `max_abs_error_rad=0.128553` 包含从约 `-0.15 rad` 到 `+0.05 rad` 的启动/过渡样本，不能直接用于判断延迟。筛选目标保持段（仿真值接近 `+0.05 rad`，最后约 2 秒）得到 25 个样本：仿真均值约 `0.05000075 rad`、标准差 `3.9e-9 rad`；真机均值约 `0.0431754 rad`、标准差 `1.78e-4 rad`；误差均值约 `-0.0068253 rad`（`-0.391°`），无明显漂移或持续跟随滞后。当前证据更符合稳定静态偏差/量化波动，不支持“持续控制延时”结论。下一步应从相反方向接近同一目标，或用对称负目标做稳定段比较，以区分固定 offset 与方向回差；在此之前不要修改正式 MuJoCo/URDF 映射。
- 2026-09-10：方向回差复测方案：左 J5 先稳定在 `-0.15 rad`，启动只记录左臂的监视器，随后通过现有控制链将同一关节改到 `+0.05 rad` 并保持 5 秒；只取到达后的最后 2 秒作为“负侧接近 +0.05”的稳定窗口。将该窗口与上一轮“正侧/直接到达 +0.05”的窗口比较真机均值。若两种接近方向的真机均值相差明显，而仿真值相同，则为方向回差；若均值接近且仅存在固定差值，则为静态 offset；若误差随时间持续变化，才继续排查控制延时。建议记录命令前后至少 12 秒，输出 `alignment/results/left_j5_approach_from_negative.csv` 及对应摘要；本步骤不修改真机、MuJoCo 或 URDF 参数。
- 2026-09-10：`left_j5_approach_from_negative_summary.csv` 实际记录 12 秒内仿真始终为 `-0.149999 rad`，没有出现 `+0.05 rad` 段，因此本轮未完成方向回差测试；下一轮需先启动记录，等待约 3 秒后再发出 `+0.05 rad` 命令，并将记录时间延长到 20 秒。
- 2026-09-10：完成左 J5 从负侧接近 `+0.05 rad` 的复测。样本覆盖 `-0.15→+0.05 rad`，最后 2 秒仿真均值约 `0.0499956 rad`，真机均值约 `0.0432593 rad`，误差均值约 `-0.0067363 rad`（`-0.386°`），误差范围约 `-0.0070816～-0.0066947 rad`。与上一轮直接到达 `+0.05 rad` 的稳定误差 `-0.0068253 rad` 相差约 `0.000089 rad`（`0.005°`），差异很小，当前没有明显方向回差证据。全程摘要的 RMSE `0.00787 rad` 仍包含换向过渡，不用于静态 offset；J5 当前可暂按约 `-0.0068 rad` 的稳定比较偏差记录，正式修改映射前仍应再做一次重复验证。
- 2026-09-10：下一步计划：重复采集左 J5 的零位、`+0.05 rad` 和 `-0.05 rad` 稳定窗口，各保持 5 秒并取最后 2 秒；分别计算 `real-sim` 均值。若三点均接近 `-0.0068 rad` 且方向差异仍小，则计算稳定窗口均值作为比较侧 MuJoCo offset（约 `-0.0068 rad`），先用 `sim_offsets` 验证，不修改真机、URDF 或正式模型；若偏差随角度变化，则改查比例/映射参数。
- 2026-09-10：三点重复采集命令：记录总时长 30 秒，依次保持零位、`+0.05 rad`、`-0.05 rad`，每段至少 7 秒；后处理每段最后 2 秒。输出前缀使用 `alignment/results/left_j5_three_points`，避免覆盖历史文件。
- 2026-09-10：检查 `left_j5_three_points_samples.csv`：1501 个左 J5 样本中仿真值全程固定为 `+0.05000076 rad`，真机值约 `0.042916～0.043297 rad`，未包含零位和 `-0.05 rad` 段。该文件只能再次确认 `+0.05 rad` 稳态误差约 `-0.006706 rad`，不能用于三点 offset 或比例判断；说明手动切换目标没有进入当前仿真/控制状态，下一轮需先单独确认每个目标值确实在 `/sim/joint_states` 中变化，再开始记录。
- 2026-09-10：检查 `left_j5_zero_to_pos_summary.csv`：实际仿真范围为 `-0.05～+0.0495 rad`，因此本次是 `-0.05→+0.05 rad`，不是预期的 `0→+0.05 rad`。最后 2 秒 `+0.05 rad` 稳定段误差均值约 `-0.005974 rad`（约 `-0.342°`），误差范围约 `-0.006614～-0.005627 rad`；全程 RMSE `0.0205 rad` 包含换向过渡，不能用于静态 offset。该结果仍支持稳定固定偏差，起始目标控制需在下一轮先用 `/sim/joint_states --once` 确认。
- 2026-09-10：下一步只做一次明确的 `0→+0.05 rad` 测试：先将左 J5 置零，使用 `ros2 topic echo /sim/joint_states --once` 确认该关节确实接近 `0 rad`，再启动 12～15 秒记录器，等待约 3 秒后切换到 `+0.05 rad` 并保持。若最后 2 秒误差仍约 `-0.006～-0.007 rad`，即可用多次稳定窗口均值作为比较侧 offset；仍不修改真机、URDF 或正式 MuJoCo 参数。
- 2026-09-10：`left_j5_zero_to_pos_final` 已确认起始仿真值约 `0 rad`，随后到达 `+0.05 rad`。最后 2 秒仿真均值 `0.0493194 rad`、真机均值 `0.0432746 rad`、误差均值 `-0.0060448 rad`（约 `-0.346°`），误差范围 `-0.006671～-0.005491 rad`。与此前两个 `+0.05 rad` 稳定窗口（约 `-0.006825`、`-0.006736 rad`）同量级，已基本确认左 J5 是稳定固定偏差而非持续延时或明显回差。下一步可先用多窗口中位数约 `-0.0067 rad` 做 `sim_offsets` 比较侧验证，验证后再决定是否更新正式映射。
- 2026-09-10：左 J5 比较侧修正步骤：启动 `openarm_alignment` 时传入 `sim_offsets:='{"openarm_left_joint5": -0.0067}'`，将修正后的仿真值写入新的 CSV；该参数只计算 `sim_corrected = sim_raw - 0.0067`，不改变真机命令、MuJoCo 物理状态或 URDF。重新测 `+0.05 rad` 稳定段，若误差均值接近 0 且标准差不变，说明 offset 符号和量级正确；随后再用 `-0.05 rad` 复核。只有两侧均通过，才讨论正式映射修改。
- 2026-09-10：`left_j5_offset_test_pos` 正向验证通过。摘要包含过渡段，显示 RMSE `0.00930 rad`；筛选最后 2 秒后，修正仿真均值约 `0.0432996 rad`，真机均值约 `0.0432822 rad`，残差均值 `-1.74e-5 rad`（约 `-0.001°`），范围约 `-3.84e-4～-1.66e-6 rad`。原先约 `-0.0067 rad` 的稳定偏差已基本消除，说明 `sim_offsets=-0.0067` 的符号和量级正确。下一步只需用同一 offset 测 `-0.05 rad` 稳定段；通过后再评估是否正式写入 MuJoCo/URDF 映射。
- 2026-09-10：`left_j5_offset_test_neg` 负向验证未通过。最后 2 秒修正仿真均值约 `-0.056685 rad`，真机均值约 `-0.036812 rad`，残差约 `+0.019873 rad`（`+1.139°`），稳定且不是过渡噪声。说明单一 `sim_offsets=-0.0067` 只适用于当前正向工作点，负向存在方向相关映射/回差或目标未实际到达 `-0.05 rad`；当前禁止把该 offset 正式写入全局 MuJoCo/URDF。应保留比较侧正向 offset，进一步确认负向原始目标和反馈，再决定是否采用方向相关补偿或修正关节映射。
- 2026-09-10：下一步先做负向基线：取消 `sim_offsets`，确认 `/sim/joint_states` 中左 J5 原始值接近 `-0.05 rad`，同时确认 `/joint_states` 的真机值稳定；记录最后 2 秒的原始 `real-sim`。若原始仿真为 `-0.05` 而真机约 `-0.0368`，则负向偏差约 `+0.0132 rad`，属于方向/映射相关问题；若仿真本身不是 `-0.05`，先修正控制目标链路。未完成基线前不采用方向相关 offset，也不修改正式模型。
- 2026-09-10：`left_j5_baseline_neg` 基线确认通过：仿真和真机均稳定，仿真为 `-0.0499993 rad`，真机为 `-0.0368124 rad`，原始 `real-sim=+0.0131869 rad`（约 `+0.756°`）。因此左 J5 在正向需要约 `-0.0067 rad`、负向需要约 `+0.01319 rad` 的比较侧补偿，偏差明显依赖方向；不能用单一全局 offset 解释，也不应直接修改 URDF 零位。下一步可分别用这两个方向补偿做验证，并继续检查控制器/反馈映射是否存在死区或回差。
- 2026-09-10：确认方向相关补偿是可行的：左 J5 可暂按运动方向/到达路径选择不同比较侧误差，正向约 `-0.0067 rad`，负向约 `+0.01319 rad`。该方法适合验证和误差分析；静止保持时方向应由最近一次有效运动方向或到达路径确定，不能仅靠当前瞬时速度。正式 MuJoCo 修正应优先建模回差/死区或反馈映射，不能把两个方向值写成同一个 URDF 零位。若暂不修改节点，可分别运行两次监视器验证两个补偿值。
- 2026-09-10：J5 的方向相关补偿方法已作为后续关节测试模板：每个关节先测 `0→正目标` 稳定窗口，再测 `0→负目标` 稳定窗口；各窗口只取最后 2 秒，分别计算 `real-sim` 均值，比较正负差异后再决定单一 offset 或方向相关补偿。下一项从左 J6 开始，暂不修改正式模型。
- 2026-09-10：左 J6 正负基线完成。正向记录最后 2 秒：仿真约 `0.0478740 rad`，真机约 `0.0265126 rad`，`real-sim=-0.0213614 rad`（`-1.224°`）；负向记录最后 2 秒：仿真约 `-0.0504043 rad`，真机约 `-0.0346189 rad`，`real-sim=+0.0157854 rad`（`+0.904°`）。正负偏差差异约 `0.03715 rad`（`2.13°`），不能用单一 offset；J6 暂按方向相关补偿候选值记录，正式修正前需重复确认并检查映射/回差来源。
- 2026-09-10：后续顺序确认：继续逐轴测试左臂剩余关节（J1～J4、J7 及手指关节），每轴采集正负稳定窗口并记录方向偏差。全部数据完成后，先生成每轴 `offset_positive`、`offset_negative` 和回差幅度表，再在 MuJoCo/监视器中实现方向相关比较补偿；不能把不同关节或不同方向的偏差直接平均成一个全局 offset。补偿验证通过后，才评估是否需要正式更新 MuJoCo/URDF 映射。
- 2026-09-10：根据用户确认，已有稳定静态数据的关节不重复采集。`left_arm_static_gap_summary.csv` 中左 J1～J4、J7 和左手指样本量为 251、标准差约 `0～1.9e-4 rad`，可直接作为初始固定偏差候选；左 J5、J6 已发现方向相关偏差，使用各自正负稳定窗口数据。只有当后续需要验证这些关节是否也存在方向回差时，才单独补测正负方向。
- 2026-09-10：左臂阶段性完成，转入右臂偏差计算。右侧已有稳定静态数据（`right_left_static_gap_summary.csv`，每关节 250 样本），先直接计算固定偏差候选，不重复采集；若后续发现方向不一致，再单独补测该关节的正负方向。
- 2026-09-10：右 J2/J6/右手指 J1 的联合 offset 验证结果不能直接用于判定。摘要中 J2 真机为 `-0.000572 rad`、右手指真机为 `-0.074197 rad`，与候选值来源的原始静态姿态（J2 约 `-0.005913 rad`、手指约 `+0.024987 rad`）不同，说明测试时关节姿态/目标点没有保持一致；J6 也存在真机值波动。不同姿态下直接套用单点静态 offset 会产生假失败，当前不修改右侧模型。下一步应每次只测一个关节，在与基线相同的目标姿态保持 5 秒，再验证对应 offset。
- 2026-09-10：右 J2/J6/右手指 J1 重测得到稳定本轮基线。J2：`real-sim=-0.00070322 rad`（`-0.040°`），可视为很小；J6：`+0.00535441 rad`（`+0.307°`）；右手指 J1：`-0.07420614 rad`（`-4.252°`）。候选比较侧 offset 分别为 `-0.00070322`、`+0.00535441`、`-0.07420614`，但这些值只适用于本轮实际姿态；尤其手指偏差很大，正式修正前必须确认关节目标、反馈映射和姿态定义。
- 2026-09-10：右 J6 方向测试完成。最后 2 秒正向稳定段：仿真 `0.05040429 rad`、真机 `0.03757534 rad`、误差 `-0.01282895 rad`（`-0.735°`）；负向稳定段：仿真 `-0.04787396 rad`、真机 `-0.03795682 rad`、误差 `+0.00991714 rad`（`+0.568°`）。正负误差相差约 `0.02275 rad`（`1.30°`），确认存在方向相关偏差；右 J6 不应使用单一 offset。候选比较侧补偿为正向 `-0.01283 rad`、负向 `+0.00992 rad`。
- 2026-09-10：方向误差统一落地流程（后续操作只按本文件执行）：
  1. 保留真机 `/joint_states` 原始反馈，不修改真机零位和控制器参数。
  2. 将每个关节的方向补偿整理为 `offset_positive`、`offset_negative`；当前已确认：左 J5=`(-0.0067,+0.01319)`，左 J6=`(-0.02136,+0.01579)`，右 J6=`(-0.01283,+0.00992)`，括号顺序为正向、负向。其他关节先沿用已有固定静态偏差，未证明有回差的关节不增加方向补偿。
  3. 第一阶段只在对齐监视器比较侧实现：根据最近一次有效运动方向选择 offset；静止保持时沿用该方向；输出 `sim_corrected`、原始 `sim_raw`、原始 `real` 和所选方向，禁止覆盖原始数据。
  4. 每个方向各复测一次稳定窗口（保持 5 秒，取最后 2 秒），要求修正后残差均值接近 0，且标准差不明显增加；失败时只调整该关节对应方向值。
  5. 全部关节验证通过后，再在 MuJoCo 中实现等价的方向相关映射/回差模型；URDF 只修改真实的静态零位或关节方向，不把方向补偿写成单一零位。
  6. MuJoCo 正式修改后重复同一批正负稳定测试，并与真机原始反馈比较；只有结果稳定、方向切换无跳变，才接受正式映射。
- 2026-09-10：已在 `openarm_alignment` 监视器加入 `sim_direction_offsets` 参数并完成构建。参数格式为 `{"joint":{"positive":offset_pos,"negative":offset_neg}}`；节点根据原始仿真角度的最近一次有效变化方向选择补偿，静止时保持上次方向，输出仍保留修正后的仿真值与真机原始值。该功能是比较侧后处理，不改变 MuJoCo 物理状态。当前候选命令：
  ```bash
  ros2 launch openarm_alignment alignment_monitor.launch.py \
    movement_epsilon_rad:=0.001 \
    sim_direction_offsets:='{"openarm_left_joint5":{"positive":-0.0067,"negative":0.01319},"openarm_left_joint6":{"positive":-0.02136,"negative":0.01579},"openarm_right_joint6":{"positive":-0.01283,"negative":0.00992}}' \
    csv_path:=alignment/results/directional_offset_test.csv \
    summary_path:=alignment/results/directional_offset_test_summary.csv
  ```
  先在小角度下验证正向、负向和换向；通过后再把右侧其他已确认固定偏差加入普通 `sim_offsets`，不要把未经方向测试的关节加入方向表。
- 2026-09-10：`directional_offset_test_summary.csv` 不能作为方向补偿验证结果：左 J5、左 J6、右 J6 的 `same_direction_samples` 与 `opposite_direction_samples` 均为 0，说明记录期间没有有效运动方向，节点沿用了初始/默认补偿。必须在记录器运行期间实际完成正向和负向移动，再分别检查移动后的稳定窗口；静止摘要不能证明方向表已生效。
- 2026-09-10：再次检查方向测试文件：左 J5/J6 仿真值基本静止，右 J6 虽有仿真变化但方向字段仍全为 `insufficient_motion`。已开放 `movement_epsilon_rad` launch 参数并重新构建；下一轮可用 `movement_epsilon_rad:=0.001`，降低方向检测阈值，但仍必须确认真机和仿真在记录期间实际执行了正负移动。
- 2026-09-10：`directional_offset_test2_summary.csv` 仅右 J6 出现 2 个 `same_direction` 样本，左 J5/J6 的方向计数仍为 0；统计量远不足以验收方向补偿。右 J6 全程摘要 RMSE `0.00544 rad` 仍混入换向段，左 J5/J6 也混入多个目标状态。下一步应分关节单独运行，确认仿真值确实发生正负变化，并以样本中的稳定窗口计算修正后残差；不能用本轮汇总直接修改补偿表。
- 2026-09-10：独立方向验证操作：一次只运行一个目标关节，其他关节保持不动；启动监视器后依次执行 `0→+0.05→-0.05`，每个目标保持 5 秒。左 J5、左 J6、右 J6 分别使用独立输出文件，避免多个关节同时运动导致方向无法对应。验证时先不加方向补偿，先取得原始正负稳定误差，再单独传入该关节的两个方向 offset 复测。
- 2026-09-10：左 J5 独立原始测试覆盖 `-0.05、0、+0.05 rad`，但 `direction` 字段 955 个样本全为 `insufficient_motion`，原因是仿真与真机变化未在同一采样周期同时超过阈值。按仿真角度分段可见：负向段平均误差约 `+0.0126 rad`，零位段约 `-0.00644 rad`，正向段约 `-0.00769 rad`；全程摘要 RMSE `0.01069 rad` 混合了过渡过程。该文件可用于确认正负偏差差异，但不能用 `same/opposite` 计数验收；方向补偿验证应按目标角度和时间稳定窗口分段。
- 2026-09-10：最终比较验证方案：使用已确认的方向补偿（左 J5、左 J6、右 J6）和已有固定偏差候选，对 MuJoCo 输出做比较侧修正；保留原始真机反馈和原始仿真值。启动后按顺序执行左 J5、左 J6、右 J6 的 `0→+0.05→-0.05`，每个目标保持 5 秒；分别比较修正前后最后 2 秒残差和 RMSE。当前实现不改变 MuJoCo 物理状态；若要物理化回差，需另建经过验证的关节回差/死区模型，不能直接改 URDF 零位。
- 2026-09-10：检查 `final_directional_alignment_summary.csv`：本轮为混合全过程摘要，不能直接用总 RMSE 验收。按修正后仿真角度分段，左 J5 在负向约 `-0.038 rad` 段残差均值约 `-4.8e-5 rad`，正向约 `+0.043 rad` 段约 `+1.5e-4 rad`，方向补偿有效；右 J6 在负向约 `-0.038 rad` 段残差约 `-8.6e-4 rad`，基本有效。左 J6 未形成清晰的正负稳定段，暂不验收其方向补偿。当前只能接受左 J5、右 J6 的比较侧修正，左 J6 需单独重测。
- 2026-09-10：左 J6 单独方向测试结果：共 526 个样本，方向计数仅 `same=1`、`opposite=2`，不足以验收。修正后负向约 `-0.0346 rad` 段有 121 个样本，残差均值约 `-0.000505 rad`，表现良好；正向约 `+0.0324 rad` 仅 1 个样本，无法评价。左 J6 仍保持“未验收”状态，需重新执行并确保正向目标保持完整 5 秒。
- 2026-09-10：左 J6 `final_directional2` 复测中，正向修正段约 `+0.0265 rad` 有 412 个样本，残差均值约 `+3.9e-5 rad`，正向通过；负向段仿真约 `-0.0346 rad` 时真机仍停在 `+0.0265 rad`，产生约 `+0.061 rad` 的不同步残差，不能视为负向补偿失败。该轮左 J6 仍未完成双向验收，需确保真机实际到达负向后再取稳定窗口。
- 2026-09-10：左 J6 负向单独复测通过。最后约 100 个稳定样本中，修正后仿真约 `-0.0346143 rad`，真机约 `-0.0345～-0.0349 rad`，残差均值约 `-1.99e-5 rad`，范围 `-2.91e-4～+9.07e-5 rad`。摘要总 RMSE `0.01872 rad` 包含从正向切换到负向的过渡，不能作为静态验收指标；负向方向补偿 `+0.01579 rad` 已验证有效。
- 2026-09-10：按用户要求暂不加入手指关节，已将手臂固定偏差和已验证的方向偏差保存到 `alignment/mujoco_arm_offsets.json`。`sim_offsets` 包含右 J1～J5、J7 和左 J1～J4、J7；`sim_direction_offsets` 包含左 J5、左 J6、右 J6。启动监视器时同时传入这两组 JSON，方向值会优先于同名固定值；该文件用于 MuJoCo 对齐比较，不改变 MuJoCo 物理状态。启动前必须完成一次全臂稳定复测，确认总体 RMSE 和各关节最后 2 秒残差均下降。

### A-084：MuJoCo 迁移到 Isaac Sim/Isaac Lab 的最短路线

目标是保留现有 ROS2 对齐工具和真机反馈链路，只替换仿真后端。不要先重写 `capture_static_gap.py`、`openarm_alignment` 或真机驱动；先让 Isaac Sim 输出与 MuJoCo 相同的 ROS2 接口，再逐步替换控制和训练任务。

#### 1. 环境隔离

`openarm_isaac_lab` 当前 README 的测试组合是 Ubuntu 22.04、Isaac Sim 5.1.0、Isaac Lab 2.3.0、Python 3.11，并提供 Docker 和本地安装方式。ROS Jazzy 的 `rclpy` 使用系统 Python 3.12；Isaac Lab 使用自己的 Python 3.11 环境，两个环境不能混用。此前出现的 `rclpy._rclpy_pybind11` 缺失就是 Python 版本混用造成的。

最省事的首轮验证使用 Docker；已有可用 Isaac Sim/Isaac Lab 环境时才使用本地安装：

```bash
cd ~
git clone https://github.com/enactic/openarm_isaac_lab.git

# Docker 路线（在 NVIDIA Isaac Lab 2.3.0 容器内执行后两行）
docker pull nvcr.io/nvidia/isaac-lab:2.3.0
cd ~/openarm_isaac_lab
python -m pip install -e source/openarm
python ./scripts/tools/list_envs.py
```

先以 `list_envs.py` 确认环境和任务可发现，再运行仓库中已有的 OpenArm 任务（例如 `Isaac-Reach-OpenArm-v0`）。该仓库的 teleoperation 和 sim-to-real 接口仍在开发中，因此 ROS2 桥接需要在本地补一层适配。

#### 2. 第一阶段只替换状态源

保留当前接口约定：

| 用途 | ROS2 接口 | 消息和单位 |
| --- | --- | --- |
| Isaac 仿真反馈 | `/sim/joint_states` | `sensor_msgs/msg/JointState`，弧度 |
| 真机反馈 | `/joint_states` | `sensor_msgs/msg/JointState`，弧度 |
| 仿真命令 | `/sim/joint_command`（或现有仿真命令接口） | 关节名和目标位置，弧度 |

关节名称和顺序必须继续使用 `openarm_right_joint1...7`、`openarm_left_joint1...7` 以及现有手指名称。Isaac 不得把状态发布到 `/joint_states`，否则会覆盖真机反馈。这样 `alignment_monitor.launch.py` 和现有 CSV 采集脚本可以原样复用。

在 Isaac Sim 的 Action Graph 中建立最小闭环：

1. `On Playback Tick` 驱动图执行。
2. `Isaac Read Joint State` 读取 OpenArm articulation 的关节名、位置和速度。
3. 将这些输出连接到 `ROS2 Publish Joint State`，话题设为 `/sim/joint_states`。
4. 需要从 ROS 控制仿真时，再增加 `ROS2 Subscribe Joint State`，将目标位置连接到 `Articulation Controller`；命令话题使用 `/sim/joint_command`，不要接到真机控制话题。

Isaac Sim 官方 ROS2 节点支持发布 `sensor_msgs/JointState`；官方示例也是把 `Isaac Read Joint State` 的名称、位置、速度等输出接到 `ROS2 Publish Joint State`。ROS2 Bridge 必须在播放期间运行，启动 Isaac Sim 前先 source ROS2 环境。

#### 3. 用现有工具验收桥接

先不要移动真机，单独启动 Isaac Sim 并检查：

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic echo /sim/joint_states --once
ros2 topic hz /sim/joint_states
```

确认四点后再接入真机：关节名完全匹配、角度为弧度、发布频率稳定（至少 20 Hz）、Isaac 不发布 `/joint_states`。随后启动现有监视器和静态采集器，输出新的 Isaac 文件名，例如：

```bash
source /opt/ros/jazzy/setup.bash
source ~/openarm_ws/install/setup.bash
ros2 launch openarm_alignment alignment_monitor.launch.py \
  csv_path:=alignment/results/isaac_arm_baseline.csv \
  summary_path:=alignment/results/isaac_arm_baseline_summary.csv
```

第一轮只记录原始 Isaac 值，不传入 `alignment/mujoco_arm_offsets.json`。MuJoCo 的 offset 和方向补偿是历史比较参数，不能假定在 Isaac 的驱动、摩擦、限位和时间步长下仍然成立。等 Isaac 的正负稳定段重新测完，再单独建立 Isaac 配置文件。

#### 4. 第二阶段再迁移控制和任务

状态桥接通过后，才把现有 MuJoCo 的控制命令、关节限位、阻尼/摩擦和回差模型逐项映射到 Isaac articulation actuator。优先迁移一个单臂、一个关节的 reach 测试，再扩展到全臂、双臂和手指。每迁移一项都保留同一套 `0→正目标→负目标` 稳定窗口测试，比较最后 2 秒的 `real-sim` 均值、RMSE 和方向差异。

迁移验收条件：

- `/sim/joint_states` 的名称、顺序、单位和时间戳正确；
- 单臂静态目标可以稳定保持，未运动关节不漂移；
- 同一目标从正、负两个方向接近时，残差和回差都单独记录；
- 原始真机反馈始终保留，offset 只用于 Isaac 比较侧或明确的 Isaac 映射配置；
- 全部关节通过后才迁移双臂任务和策略训练。

本阶段不修改真机零位，不把 MuJoCo 的方向补偿直接写入 URDF，也不把手指误差加入 Isaac。先完成“Isaac 状态 → ROS2 → 现有 gap 工具”的最小闭环，再做动力学和映射精度。

### A-085：Isaac Lab Docker 镜像下载慢时的处理

`nvcr.io/nvidia/isaac-lab:2.3.0` 约 7.5 GB，下载慢通常是到 NVIDIA NGC 的网络链路问题。不要删除当前镜像缓存；已经完成的 layer 会保留。当前下载中如果仍在增长，先让它完成；长时间无变化时按下面顺序处理。

#### 方案一：从高速机器下载后转移（最稳定）

在网络较快、显卡驱动兼容的另一台 Linux 机器或服务器上执行：

```bash
docker pull nvcr.io/nvidia/isaac-lab:2.3.0
docker save nvcr.io/nvidia/isaac-lab:2.3.0 | zstd -T0 -o isaac-lab-2.3.0.tar.zst
```

把 `isaac-lab-2.3.0.tar.zst` 通过局域网、移动硬盘或 `scp` 传到本机，再执行：

```bash
zstd -d isaac-lab-2.3.0.tar.zst -c | docker load
docker images nvcr.io/nvidia/isaac-lab
```

这样只需让一台机器访问 NGC，本机不再重复下载 7.5 GB。应使用官方镜像导出文件，不要从不明 Docker 镜像代理导入同名镜像。

#### 方案二：给 Docker daemon 配置已有的网络代理

如果本机已有可用 HTTP/HTTPS 代理（下面的端口只是示例），代理必须配置给 Docker daemon，单纯在当前 shell 设置变量通常不够：

```bash
sudo systemctl edit docker
```

填入并替换实际代理地址：

```ini
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
Environment="NO_PROXY=localhost,127.0.0.1"
```

然后：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
docker pull nvcr.io/nvidia/isaac-lab:2.3.0
```

Docker 官方支持通过 daemon 的代理配置进行镜像拉取；代理端口必须替换为本机实际端口。

#### 方案三：降低并发、增加重试

网络不稳定时，Docker 默认同时下载多个 layer，可能导致超时。若当前下载已经长时间无变化，可停止后配置 `/etc/docker/daemon.json`（若已有内容，合并字段，不要覆盖原配置）：

```json
{
  "max-concurrent-downloads": 1,
  "max-download-attempts": 10
}
```

重启 Docker 后重新执行原命令：

```bash
sudo systemctl restart docker
docker pull nvcr.io/nvidia/isaac-lab:2.3.0
```

这个方案的目标是减少断线和重试，单纯降低并发不一定提高峰值速度。不要配置只针对 Docker Hub 的随机 registry mirror 来替代 `nvcr.io`，因为它们通常没有 NVIDIA NGC 镜像，或无法保证镜像 digest 一致。

首选顺序：高速机器导出并 `docker load`；其次使用已有代理；最后才调整并发和重试。镜像下载完成后再继续 Isaac Sim/ROS2 桥接，不要在下载未完成时修改 MuJoCo 或真机配置。

### A-086：国内镜像候选与安全检查

Docker 的 `registry-mirrors` 主要针对 Docker Hub，不能把 `nvcr.io` 自动变成国内镜像；Docker 官方也说明镜像缓存不能直接镜像另一个 registry。因此，像 DaoCloud、Docker Proxy 这类服务即使能加速 Docker Hub，也不保证能代理 `nvcr.io/nvidia/isaac-lab`。

目前可以尝试的候选是 Docker Hub 上的社区同步镜像：

```text
beclab/nvidia-isaac-lab:2.3.0
```

该仓库公开列出了 `2.3.0` 的 `linux/amd64` 标签，压缩大小约 7.88 GB；它不是 NVIDIA 官方仓库，使用前必须先比较 digest。先查询两边的 amd64 digest：

```bash
docker buildx imagetools inspect nvcr.io/nvidia/isaac-lab:2.3.0 | grep -E 'Digest|linux/amd64'
docker buildx imagetools inspect beclab/nvidia-isaac-lab:2.3.0 | grep -E 'Digest|linux/amd64'
```

只有 digest 完全一致，才可以通过国内 Docker Hub 代理尝试下载并改回原标签（代理地址可用性会变化）：

```bash
docker pull dockerproxy.net/beclab/nvidia-isaac-lab:2.3.0
docker tag dockerproxy.net/beclab/nvidia-isaac-lab:2.3.0 nvcr.io/nvidia/isaac-lab:2.3.0
```

如果 digest 不一致，不要把这个镜像用于正式 Isaac Lab 环境；继续使用官方 NGC 镜像，或采用代理配置、云端下载后导入的方案。Docker Proxy 的文档只保证其 Docker Hub 代理用途，不能据此证明 NVIDIA NGC 镜像来源或内容正确。

可选测试顺序：

1. 先执行 `docker buildx imagetools inspect`，确认社区镜像存在且 digest 一致。
2. 再用 `dockerproxy.net/beclab/...` 测试下载速度；速度不稳定就立即停止，不要反复删除缓存。
3. 下载完成后用 `docker image inspect nvcr.io/nvidia/isaac-lab:2.3.0 --format '{{.Id}}'` 记录本地镜像 ID。
4. 若无法确认 digest，放弃社区镜像，使用官方 NGC + daemon 代理或本地离线导入。

#### 没有 `docker buildx` 时

Ubuntu 打包版 Docker 可能没有 buildx 插件。可以用 `docker manifest inspect` 查询 manifest；它只查询元数据，不会下载镜像层：

```bash
docker manifest inspect nvcr.io/nvidia/isaac-lab:2.3.0 \
  | jq -r '.manifests[] | select(.platform.os=="linux" and .platform.architecture=="amd64") | .digest'

docker manifest inspect beclab/nvidia-isaac-lab:2.3.0 \
  | jq -r '.manifests[] | select(.platform.os=="linux" and .platform.architecture=="amd64") | .digest'
```

两条命令输出完全相同，才允许使用社区镜像。如果提示 `jq: command not found`，先安装 `jq`，或去掉管道查看完整 JSON。若提示 DNS 或 registry 连接失败，只能说明当前网络无法访问 registry，不能据此判定 digest 不同。

- 2026-09-11：已完成官方 NGC 与 Docker Hub 社区镜像的 amd64 digest 校验，两者均为 `sha256:f1eae1f847cc77e00738d919138d78dde9a12589da9a83b4909555a4abeddb20`。内容一致，可以使用 `dockerproxy.net/beclab/nvidia-isaac-lab:2.3.0` 下载，再重新标记为 `nvcr.io/nvidia/isaac-lab:2.3.0`；仍需在本机执行镜像 ID 检查，确认下载完整。

- 2026-09-11：`dockerproxy.net` 下载在 TLS 握手阶段超时，未开始拉取镜像层，digest 校验结论不变。下一步改用 DaoCloud 的 Docker Hub 前缀 `m.daocloud.io/docker.io/...`，先执行 manifest 检查，确认可访问后再拉取；若多个国内代理均 TLS 超时，则只能使用已有网络代理或官方 NGC。
- 2026-09-11：DaoCloud 返回 allowlist 拒绝（该镜像不在白名单），因此不能使用 `m.daocloud.io/docker.io/...`。可改试支持 Docker Hub 的国内代理 `docker.1ms.run` 或 `docker.1panel.dev`，仍需先检查 amd64 digest，且只对已验证的 `beclab/nvidia-isaac-lab:2.3.0` 使用；这些服务不是 NVIDIA 官方 registry。
- 2026-09-11：`docker.1ms.run` 的 manifest 查询长时间无输出，判断为代理入口网络/TLS 卡住。后续所有代理检查命令统一加 `timeout 20s`；超时即放弃该入口，不删除本地 Docker layer，也不重复等待。
- 2026-09-11：对 `docker.1ms.run/beclab/nvidia-isaac-lab:2.3.0` 执行 20 秒限时检查，返回码 `124`，确认该代理入口超时。下一候选为 `docker.1panel.dev`，仍需先检查 manifest 和官方 digest，再开始 7.88 GB 下载。
- 2026-09-11：检查本机 Isaac 环境：发现源码仓库 `~/openarm_isaac_lab` 已存在，但未发现 `isaacsim`、`isaac-sim` 可执行文件，未发现 Isaac Sim/Isaac Lab 常见安装目录，Conda 中没有 `env_isaaclab`，Python 环境没有 Isaac/Omniverse 包，Docker 中也没有 Isaac/Omniverse 镜像。因此当前只有 OpenArm Isaac Lab 源码，Isaac Sim runtime 尚未安装。
- 2026-09-11：检查本机 pip 安装前置条件：系统为 x86_64、GLIBC 2.39（满足 Isaac Sim 5.x pip 安装要求），磁盘剩余约 320 GB；但 `nvidia-smi` 无法连接 NVIDIA driver，当前 GPU 驱动不可用。pip 包可以先下载，Isaac Sim 在驱动修复前不能正常启动。
- 2026-09-11：确认 `.deb` 不是 Isaac Sim 5.1.0 的官方安装格式。若 Docker/NGC 太慢，官方 workstation standalone ZIP 是更适合本机的替代方案，可用 `aria2c` 多连接和断点续传从 `downloads.isaacsim.nvidia.com` 下载；仍需先修复 NVIDIA driver，再运行 GUI 或 Isaac Lab。

### A-091：不用 Docker，改用 pip 安装 Isaac Sim 5.1.0

如果“dep”指的是 `pip`，Isaac Lab 2.3.0 官方文档提供了从 NVIDIA PyPI 安装 Isaac Sim 5.1.0 的方法：使用 Python 3.11，安装 `isaacsim[all,extscache]`，再安装 Isaac Lab 源码。该方式绕开 7.5 GB Docker 镜像，但仍需下载 Isaac Sim 的多个 wheel，速度取决于 `pypi.nvidia.com`；没有可确认的官方国内镜像。`.deb` 不是官方安装方式。

本机 GLIBC 2.39 和 x86_64 满足 pip 路线的基本条件，但当前 `nvidia-smi` 无法连接 NVIDIA driver。先修复驱动并确认 `nvidia-smi` 正常，再投入大流量下载。

```bash
# 不要在 base(Python 3.13) 或 ROS Jazzy 环境中安装
conda create -n env_isaaclab python=3.11 -y
conda activate env_isaaclab
python -m pip install --upgrade pip

# Isaac Sim 5.1.0（官方 NVIDIA PyPI）
python -m pip install "isaacsim[all,extscache]==5.1.0" \
  --extra-index-url https://pypi.nvidia.com \
  --retries 10 --timeout 120

# 与 Isaac Sim 5.1/Isaac Lab 2.3 匹配的 PyTorch（按 CUDA 驱动情况调整）
python -m pip install -U torch==2.7.0 torchvision==0.22.0 \
  --index-url https://download.pytorch.org/whl/cu128 \
  --retries 10 --timeout 120

# 安装 Isaac Lab 2.3.0
cd ~
git clone --branch v2.3.0 --depth 1 https://github.com/isaac-sim/IsaacLab.git
cd ~/IsaacLab
./isaaclab.sh --install

# 安装 OpenArm Isaac Lab 项目
cd ~/openarm_isaac_lab
python -m pip install -e source/openarm
python ./scripts/tools/list_envs.py
```

安装完成后，在同一个 `env_isaaclab` 环境中验证：

```bash
isaacsim
cd ~/IsaacLab
./isaaclab.sh -p scripts/tutorials/00_sim/create_empty.py
```

ROS2 Jazzy 的命令和 `openarm_alignment` 仍在另一个终端执行，不能把 `env_isaaclab` 的 Python 用来运行 ROS2 `rclpy` 节点。

### A-092：standalone ZIP 已下载但尚未解压

2026-09-11：官方 standalone ZIP 已下载到 `~/Downloads/isaacsim/isaac-sim-standalone-5.1.0-linux-x86_64.zip`。直接执行 `cd ~/isaacsim` 会失败，因为 `~/isaacsim` 只是准备作为解压目录，目前尚未创建。先解压，再运行 `post_install.sh`：

```bash
mkdir -p ~/isaacsim
unzip ~/Downloads/isaacsim/isaac-sim-standalone-5.1.0-linux-x86_64.zip -d ~/isaacsim
cd ~/isaacsim
chmod +x post_install.sh
./post_install.sh
```

如果解压后根目录没有 `post_install.sh`，查找实际位置：

```bash
find ~/isaacsim -maxdepth 3 -name post_install.sh -print
```

进入该脚本所在目录后再执行 `./post_install.sh`。安装完成后可用 `test -x ~/isaacsim/isaac-sim.sh && echo OK` 检查主启动脚本。Isaac Sim 的图形启动仍要求 NVIDIA 驱动正常，先用 `nvidia-smi` 验证驱动状态。

### A-093：standalone 安装完成后的首次启动

2026-09-11：`~/isaacsim/isaac-sim.sh` 已存在，`nvidia-smi` 已正常识别 RTX 5090（驱动 595.84）。`nvidia-smi` 同时显示两个 `kit` 进程并占用约 29 GB 显存，可能已有 Isaac Sim 实例在运行；启动前先确认，避免重复打开实例。

```bash
cd ~/isaacsim
ps -ef | grep -E 'isaac|kit' | grep -v grep
```

如果已经有 Isaac Sim 窗口，直接使用该窗口。如果没有窗口且确认没有正在运行的实例，按官方顺序执行：

```bash
cd ~/isaacsim
./post_install.sh                 # 只需成功执行一次
./isaac-sim.selector.sh           # 打开 App Selector，选择 Isaac Sim Full 后 START
```

首次启动可能需要等待 5–10 分钟。若只想先做无界面兼容性检查，可执行：

```bash
cd ~/isaacsim
./isaac-sim.compatibility_check.sh --/app/quitAfter=10 --no-window
```

官方 5.1.0 的 standalone 安装流程也是解压后运行 `post_install.sh`，再运行 `isaac-sim.selector.sh`。[NVIDIA Workstation Installation](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_workstation.html)

### A-094：将内部 `intern_data_engin` 框架接入 Isaac Sim 对齐

2026-09-11：收到内部仓库地址 `http://192.168.18.200:53000/EmbodiedAI/intern_data_engin.git`。当前环境访问该地址时需要仓库认证，无法直接读取其 README 和代码，因此不能凭仓库名称断言它的具体 API。仓库名看起来像数据工程/数据采集框架；正式接入前必须先在本机克隆并确认入口、配置格式和数据 schema。

先在能访问内网 Git 服务的终端执行：

```bash
cd ~/openarm_ws
git clone http://192.168.18.200:53000/EmbodiedAI/intern_data_engin.git intern_data_engin
cd intern_data_engin
find . -maxdepth 2 -type f | sort | head -100
sed -n '1,240p' README.md
```

本项目迁移到 Isaac Sim 时采用最小改动方案：保留现有 `alignment/capture_static_gap.py` 和所有 CSV 统计逻辑，只把 MuJoCo 的仿真状态源替换为 Isaac Sim 状态源。数据流应固定为：

```text
Isaac Sim 5.1.0 + OpenArm USD/Isaac Lab
             │  ROS 2 bridge
             ▼
      /sim/joint_states   ─┐
                            ├─ alignment/capture_static_gap.py
真机 ros2_control         ─┘   (/joint_states)
      /joint_states
```

Isaac Sim 端必须发布 `sensor_msgs/msg/JointState`，关节名与真机完全一致（例如 `openarm_left_joint6`），并使用弧度。真机原始 `/joint_states` 保持不变；所有固定误差和方向误差只作为 Isaac Sim 侧的比较变换输入，不能修改真机反馈。这样可以继续使用现有的 5 秒稳定段、最后 2 秒截取和 RMSE/平均误差计算。

接入顺序：

1. 先按内部框架 README 安装其依赖，但不要改动 `alignment/capture_static_gap.py`。
2. 在 `openarm_isaac_lab` 中启动 OpenArm USD/Articulation，并启用 Isaac Sim ROS 2 bridge；先只验证 `/sim/joint_states` 的消息频率、关节名和位置单位。
3. 将内部数据引擎配置为读取 `/sim/joint_states` 与 `/joint_states`，或让它调用现有 capture 脚本；两者不要同时写同一个 CSV。
4. 先做单关节 smoke test（左 J5 或左 J6），再做左右臂全关节静态对齐。每次测试保留 raw CSV，校正后的 CSV 使用单独文件名。
5. 只有当 Isaac Sim 原始状态与真机稳定段的残差确认后，才把经过验证的映射写入 Isaac Sim/URDF。方向回差仍应在数据层记录，不能用一个固定 offset 强行覆盖。

当前已知的临时校正文件是 `alignment/mujoco_arm_offsets.json`；它是 MuJoCo 比较阶段的记录，不能直接当作 Isaac Sim 的正式映射。Isaac Sim 接入后应复制为单独的 `alignment/isaacsim_offsets.json`，并在结果中同时保存 `sim_raw_position_rad`、`sim_corrected_position_rad` 和 `real_position_rad`。

### A-095：Isaac Sim 首次启动日志正常

2026-09-11：App Selector 已显示 `app ready`，并启动了：

```text
/home/tangyuan/isaacsim/isaac-sim.sh --/isaac/startup/ros_bridge_extension= --/rtx/ecoMode/enabled=True
```

这表示 Isaac Sim 主程序正在加载，ROS 2 Bridge 启动参数已经传入。此时不要再启动第二个 Isaac Sim 实例；先等待 GUI 完全出现（首次启动可能需要数分钟）。GUI 出现后，在另一个终端验证：

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic list | grep -E 'joint_states|rosout'
```

当前只看到 `/rosout` 也不算失败，因为 Isaac Sim 尚未加载 OpenArm 场景和 JointState 发布图。下一步是从 `openarm_isaac_lab` 加载 OpenArm USD，并建立 ROS 2 JointState 发布器；发布器就绪后再检查：

```bash
ros2 topic echo /sim/joint_states --once
```

### A-096：重新打开 Isaac Sim GUI

如果 GUI 被关闭，先检查是否有残留实例：

```bash
pgrep -af 'isaac-sim|kit' || true
```

确认没有需要保留的 Isaac Sim 实例后，在终端执行：

```bash
cd ~/isaacsim
./isaac-sim.selector.sh
```

在 App Selector 中选择 **Isaac Sim Full**，点击 **START**。不要同时启动多个 GUI 实例，否则可能因为 RTX 5090 显存已被占用而启动失败。

### A-097：App Selector 成功但 Isaac Sim Full 启动后崩溃

2026-09-11：最近一次启动中 App Selector 正常到达 `app ready`，但 Isaac Sim Full 在约 13 秒后于 `librtx.scenedb.plugin.so` 崩溃。崩溃日志记录启动时已有两个计算进程占用约 8.4 GB 和 15.2 GB 显存，GPU 几乎没有可用显存；因此本次不是 ZIP 损坏或 `post_install.sh` 问题，而是 GPU 资源冲突/RTX 初始化失败。

重试前按以下顺序操作：

```bash
# 1. 确认没有遗留的 Isaac/训练进程
pgrep -af 'isaac-sim|kit|python' || true

# 2. 确认驱动已恢复且显存基本空闲
nvidia-smi
```

只关闭自己启动的训练或 Isaac 进程，不要结束 Xorg、GNOME 或桌面进程。若 `nvidia-smi` 仍提示无法连接驱动，先重启系统；重启后再次确认 `nvidia-smi` 正常，再运行：

```bash
cd ~/isaacsim
./isaac-sim.sh --/isaac/startup/ros_bridge_extension= --/rtx/ecoMode/enabled=True
```

这次直接运行主程序，日志会留在当前终端，便于定位；不要同时运行 `isaac-sim.selector.sh`。GUI 成功打开后再进行 ROS 2 话题检查。

### A-098：驱动恢复但显存仍被占用

2026-09-11：`nvidia-smi` 已恢复正常，但 RTX 5090 显存使用为 `27263 MiB / 32607 MiB`。占用者为：

```text
PID 2790033  .../envs/nurec-train/bin/python       8650 MiB
PID 3060569  .../release/kit/python/bin/python3   17962 MiB
```

在重新启动 Isaac Sim GUI 前，必须先结束确认可以停止的训练/仿真任务。先查看完整命令：

```bash
ps -fp 2790033 3060569
```

确认 PID 2790033 是不再需要的 `nurec-train` 后，可正常停止对应训练任务；确认 PID 3060569 是残留 Isaac Sim 后再停止它。不要结束 Xorg、GNOME、Firefox 或 VS Code 进程。停止后确认：

```bash
nvidia-smi
```

显存降到桌面占用水平后，再执行 `./isaac-sim.sh --/isaac/startup/ros_bridge_extension= --/rtx/ecoMode/enabled=True`。当前这两个 PID 在本工具环境不可直接代为结束，必须在用户桌面终端确认后操作。

### A-099：只清理 Isaac Sim 残留并重新启动

2026-09-11：用户要求保留 `nurec-train`，只结束 Isaac Sim 残留进程。使用 `/home/tangyuan/isaacsim` 路径匹配，避免误结束其他 Python 任务：

```bash
isaac_pids=$(pgrep -f '/home/tangyuan/isaacsim' || true)
if [ -n "$isaac_pids" ]; then
  echo "Isaac Sim PIDs: $isaac_pids"
  kill -TERM $isaac_pids
  sleep 5
fi

echo '--- remaining GPU compute processes ---'
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
```

确认输出中只剩 `nurec-train` 后，重新启动 Isaac Sim：

```bash
cd ~/isaacsim
./isaac-sim.sh \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
```

此流程不会结束 `nurec-train`，也不会结束 Xorg、GNOME、Firefox 或 VS Code。

### A-100：Isaac Sim 残留位于另一套安装目录

2026-09-11：实际残留进程不是 `~/isaacsim`，而是另一套 Isaac Sim 6.0 安装：

```text
PID 3071373  /home/tangyuan/lixi/isaacsim6.0_release/6.0_release/kit/python/bin/python3
```

PID 2790033 `/home/worker/.conda/envs/nurec-train/bin/python` 是训练进程，必须保留。只结束确认过的 Isaac Sim PID：

```bash
ps -fp 3071373
kill -TERM 3071373
sleep 5
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
```

如果 PID 3071373 仍存在，确认它仍是上述 Isaac Sim 路径后再执行：

```bash
kill -KILL 3071373
```

显存只剩 `nurec-train` 后，再启动 `~/isaacsim` 下的 5.1.0 版本；不要启动 `/home/tangyuan/lixi/isaacsim6.0_release`。

### A-101：确认闪退根因是 Isaac Sim 5.1 与 6.0 同时占用 GPU

2026-09-11：最新崩溃日志显示启动 Isaac Sim 5.1.0 时，GPU 上同时存在：

```text
PID 2790033  nurec-train                         6828 MiB
PID 3071373  /home/tangyuan/lixi/isaacsim6.0_release/.../python3  20190 MiB
PID 3086652  新启动的 5.1.0 kit                    26 MiB
```

随后 5.1.0 在 `librtx.scenedb.plugin.so` 段错误退出。根因是两套 Isaac Sim 争用同一块 RTX 5090，而不是 5.1.0 ZIP 或 `post_install.sh` 损坏。清理时必须匹配 6.0 的完整路径，之前只匹配 `~/isaacsim` 会漏掉它：

```bash
pgrep -af '/home/tangyuan/lixi/isaacsim6.0_release' || true
pkill -TERM -f '/home/tangyuan/lixi/isaacsim6.0_release' || true
sleep 5
pgrep -af '/home/tangyuan/lixi/isaacsim6.0_release' || true
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
```

确认 6.0 进程已经消失、只剩 `nurec-train` 后，再启动 5.1.0。若 6.0 进程自动重生，先检查其父进程再停止父进程；不要结束 `nurec-train`。

### A-102：Isaac Sim 6.0 残留属于其他用户

2026-09-11：检查发现 6.0 进程的所有者是 `user1`，父进程为 `3071368`，因此普通用户执行 `pkill` 返回“不允许的操作”。这不是命令匹配问题，而是 Linux 跨用户进程权限问题。进程树为：

```text
user1 3071368 .../python.sh source/run.py --preset=capture_preview ...
user1 3071373 .../kit/python/bin/python3 source/run.py ...
user1 3071652 .../omni.kit.telemetry...
```

只有在确认这是可以停止的残留任务后，使用管理员权限结束这套 Isaac Sim 6.0 进程；不要结束 PID 2790033 的 `nurec-train`：

```bash
sudo kill -TERM 3071368 3071373 3071652
sleep 5
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
```

如果仍有同一路径进程残留，再执行：

```bash
sudo pkill -KILL -f '/home/tangyuan/lixi/isaacsim6.0_release/6.0_release'
```

确认 6.0 进程消失后，再启动 `~/isaacsim` 的 5.1.0。

### A-103：不能在当前显存占用下并行启动自己的 Isaac Sim

2026-09-11：用户询问能否保留 `user1` 的 Isaac Sim 6.0，同时启动自己的 `~/isaacsim` 5.1.0。软件目录和 Linux 用户可以隔离，但 GPU 显存不能隔离；当前约 `20.2 GB (Isaac Sim 6.0) + 8.6 GB (nurec-train)`，RTX 5090 仅剩约 3 GB，5.1.0 GUI 会在 RTX 场景初始化阶段崩溃。

因此当前不要强行启动第二套 GUI，也不要修改或结束 `user1` 的任务。可用以下命令等待资源释放：

```bash
watch -n 2 nvidia-smi
```

等 `user1` 的 Isaac Sim 进程结束、显存恢复到桌面占用水平后，再启动自己的 5.1.0：

```bash
cd ~/isaacsim
./isaac-sim.sh \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
```

真正同时运行需要第二块 GPU、另一台机器或让 `user1` 释放 GPU；仅更换安装目录、用户或端口不能解决显存冲突。

### A-104：确认当前采集数据的使用者和任务

2026-09-11：从 GPU 进程命令可确认数据采集任务属于用户 `user1`，由 Isaac Sim 6.0 启动：

```text
/home/tangyuan/lixi/isaacsim6.0_release/6.0_release/python.sh source/run.py
  --preset=capture_preview
  simulation.mode=replay
  simulation.state_cache=outputs/state_cache/newfile_scene_cache
  capture.video=true
  camera.names=[front_tele]
  render_quality.path_tracing=false
  capture.render_subframes=1
  lidar.enabled=false
```

这表示它正在回放 `newfile_scene_cache` 并进行 `front_tele` 相机视频预览采集，不是空闲的 Isaac Sim 进程。需要确认具体输出文件时，在有权限的终端执行：

```bash
ps -o user,pid,ppid,etime,cmd -p 3071368,3071373
sudo lsof -p 3071368,3071373 | grep -E 'outputs|state_cache|newfile_scene_cache|\.usd|\.json|\.mp4' | head -80
```

不要在任务仍运行时删除或移动其 `outputs/state_cache` 文件，也不要结束该任务，除非 `user1` 确认采集已经完成。

### A-106：主机 IP 与当前任务进程

2026-09-11：读取主机状态得到：

```text
hostname: tangyuan-System-Product-Name
LAN IP:   192.168.18.154  (eno1/24)
Docker:   172.17.0.1      (docker0)
```

当前相关任务：

```text
PID 2790033  user=worker  /home/worker/.conda/envs/nurec-train/bin/python .../Instant-nurec-github/train.py --gpu 0
             显存约 8630 MiB；另有 TorchInductor 编译子进程

PID 3071368  user=user1   .../isaacsim6.0_release/6.0_release/python.sh source/run.py
             --preset=capture_preview simulation.mode=replay

PID 3071373  user=user1   .../isaacsim6.0_release/6.0_release/kit/python/bin/python3 source/run.py ...
             显存约 19951 MiB；这是实际运行的 Isaac Sim 6.0 采集进程

PID 3071652  user=user1   .../extscache/omni.kit.telemetry.../omni.telemetry.transmitter
             属于同一 Isaac Sim 6.0 任务
```

当前没有发现独立运行的 `~/isaacsim` 5.1.0 进程；之前的 5.1.0 实例已崩溃退出。

### A-105：检查是否还有其他空闲 Isaac 残留

2026-09-11：最近一次已知状态中，`user1` 的 6.0 `capture_preview` 是活动任务，`nurec-train` 是另一项计算任务；5.1.0 崩溃实例应已退出。用下面命令检查是否还有其他 Isaac 进程：

```bash
echo '--- all Isaac processes ---'
ps -eo user,pid,ppid,stat,etime,%cpu,%mem,cmd | \
  grep -E 'isaacsim|isaac-sim|kit/python|python.sh' | grep -v grep

echo '--- GPU compute processes ---'
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
```

判断规则：同一条 `capture_preview` 进程树（`python.sh`、`kit/python/bin/python3`、telemetry）属于正在使用的数据采集；`nurec-train` 保留；其余没有对应任务、且仍占用显存的 Isaac/Kit 进程才是可疑残留。先用 `ps -fp <PID>` 确认命令，再处理，不能仅按进程名结束。

### A-107：视觉、双臂协同、控制数据盘点与 Isaac Sim 对齐任务

2026-09-11：根据参数表和当前工作区的实际文件，完成第一轮数据盘点。当前结论是：关节位置 gap 已经有较多真机静态/方向数据，但视觉、双臂时序、控制延迟和接触物理还没有形成可验收的对齐数据集。2026-09-14 起，仿真统一以 Isaac Sim 为准；已有 MuJoCo action、observation、图像和 episode 只作历史审计，不再作为 Isaac Sim replay 或 sim2real 验收输入。

#### 已采集内容

| 类别 | 当前证据 | 状态和限制 |
|---|---|---|
| 关节位置/固定偏差 | `alignment/results/*summary.csv`、`mujoco_arm_offsets.json` | 已采集。左右臂 J1--J7 的静态、方向和部分动态段均有记录；J5/J6 仍需按方向分别解释，不能合并成单一 offset。 |
| 控制动作轨迹 | `dora/dora-openarm-data-collection/ker_mujoco_data/20260909-160842-b6b2d210/dataset/episodes/0/action/arms/{left,right}/state.parquet` | 历史 MuJoCo 数据：左右各 501 行、约 2.000 s，`qpos` 为 8 维；只用于审计字段和旧结果追溯，不得输入 Isaac Sim replay。 |
| 仿真观测轨迹 | 同一 session 的 `obs/arms/{left,right}/state.parquet` | 历史 MuJoCo 数据：左 273 行、右 306 行且采样不规则；不得当作 Isaac Sim 观测或 250 Hz 对齐证据。 |
| 仿真视觉 | 同一 session 的 `dataset/episodes/0/cameras/{ceiling,head_left,head_right,wrist_left,wrist_right}` | 历史 MuJoCo 图像：5 个相机各 59 张，共 295 张；不得与 Isaac Sim 图像直接配对验收。 |
| 采集元数据/映射 | session 的 `metadata.yaml`、`metadata_ker_mujoco.yaml`、`ker_mapping.yaml` | 已有设备、相机名、MuJoCo 场景和关节顺序映射。该 episode 标记为 `success: false`，任务说明明确是映射/相机验证，不是完整操作演示。 |

当前 `ker_mujoco_data` 下共有 33 个目录，但只有 `20260909-160842-b6b2d210` 含 episode 数据；其余目录主要是 metadata、dataflow 日志和映射文件，不能计入有效轨迹样本。这个结论由文件扫描得到，不代表其余目录一定没有可恢复的外部数据。

#### 仍可采集的内容

| 类别 | 需要新增的原始记录 | 最小采集方式 |
|---|---|---|
| 视觉 | 真机与 Isaac Sim 的相机内参、外参、分辨率、FPS、时间戳、曝光/光照/遮挡条件 | 固定相机和场景，采集同一棋盘格/AprilTag 和同一物体；保存原图、相机参数、时间戳，不只保存视频。 |
| 双臂协同 | 左右臂统一时钟、角色、交接位姿、同步窗口、双臂距离和相对速度 | 同一 episode 同时记录左右 action/observation；离线计算时间差、相对位姿、交接事件和同步误差。 |
| 控制 | 发布频率、命令到执行延迟、观测延迟、关节噪声、末端误差、夹爪误差 | 每条消息带单调时钟；同时记录 command、真实反馈和末端 TF；用阶跃和固定目标段分别估计延迟与稳态误差。 |
| 物体/工作区 | 物体尺寸、质量、质心、摩擦/刚度、抓取/插接/旋拧区域，桌面、夹具、障碍物和边界 | 用一个版本化 YAML/JSON 场景清单绑定 USD/URDF 资源；实测值和估计值分开写，不能只写口头参数。 |
| 接触 | 接触力、插入阻力、旋拧扭矩、碰撞/滑移阈值 | 真机侧需要力/扭矩或电流代理信号；仿真侧记录 contact wrench、接触点和事件时间。没有传感器时只能标记“未测量”，不能伪造接触指标。 |

#### Isaac Sim 还需要对齐的项目

迁移到 Isaac Sim 后，按以下顺序处理，避免把多个误差源混在一起：

1. **坐标和映射**：关节名称、顺序、单位、正方向、左右基座坐标系、关节限位、夹爪方向。先复用 `ker_mapping.yaml` 和当前 MuJoCo offset 做比较层变换，保留真机原始反馈；确认后再写入正式 USD/URDF。
2. **单臂控制**：控制频率、动作保持方式、执行器增益/阻尼、速度/加速度限幅、命令延迟和观测延迟。J5/J6 的方向回差必须用 `approach-from-positive`/`approach-from-negative` 分组，使用分段 offset 或迟滞模型，不能用一个平均值覆盖两个方向。
3. **双臂时序**：统一时间基准，验证左右 action 是否同一 tick 到达；对齐双臂基座间距、相对位姿、相对速度和交接时间窗。
4. **视觉**：相机外参/内参、坐标系、分辨率、FPS、畸变、曝光、光照、背景、遮挡和噪声。Isaac Sim 的图像必须带仿真时间戳，并与关节/动作写入同一 episode。
5. **物体、工作区和接触**：几何、质量、惯量/质心、摩擦、刚度/阻尼、夹具和障碍物边界，以及接触/插入力和滑移事件。上述参数目前没有在 `alignment/results` 中形成实测基线，属于待采集项。

#### 轨迹 replay 验证流程

先选用现有的 `20260909-160842-b6b2d210` episode 0 做**数据链路验证**，不要把它当作最终任务成功率验证：

```bash
cd ~/openarm_ws
SESSION=dora/dora-openarm-data-collection/ker_mujoco_data/20260909-160842-b6b2d210
find "$SESSION/dataset/episodes/0" -type f | sort

# 检查动作文件的行数、时间跨度和 qpos 维度（使用采集环境的 Python）
dora/dora-openarm-data-collection/.venv/bin/python - <<'PY'
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq

root = Path("dora/dora-openarm-data-collection/ker_mujoco_data/20260909-160842-b6b2d210/dataset/episodes/0")
for f in sorted(root.rglob("*.parquet")):
    t = pq.read_table(f)
    ts = np.asarray(t["timestamp"]).astype("int64")
    print(f.relative_to(root), "rows=", len(ts),
          "duration_s=", (ts[-1] - ts[0]) / 1e9,
          "qpos_dim=", len(t["qpos"][0].as_py()))
PY
```

正式 replay 时，动作 parquet 是输入源，不能用 Isaac Sim 的反馈反过来改写动作：

```text
action parquet (left + right, original timestamps)
        -> intern_data_engin / Isaac Sim adapter
        -> Isaac Sim joint controller
        -> /sim/joint_states + camera + contact log
        -> replay_metrics.py
```

每次 replay 至少输出以下结果：

- 轨迹：每个关节的时间对齐、RMSE、最大误差、峰值时间差和丢帧数；
- 双臂：左右时间差、相对位姿/距离/速度、交接窗口内的同步误差；
- 视觉：帧数、FPS、时间戳 p50/p95 抖动，以及有配对真机图像时的图像差异；
- 控制：command→feedback 延迟、观测延迟、稳态误差和噪声；
- 接触：接触开始/结束时间、法向力/扭矩、插入深度和滑移事件。

第一轮只验收**链路和时间戳完整性**。关节静态段可暂沿用约 `0.001--0.005 rad` 的已有基线；J5/J6 单独报告方向残差。双臂同步先报告实际分布，再决定是否采用“一个 250 Hz 控制 tick（约 4 ms）以内”作为目标。视觉和接触尚未有真机基线，暂不设定通过阈值。

#### 下一步执行顺序

1. 固定一条真实双臂 episode，同时保存 action、observation、五路相机原图和统一时间戳；
2. 在 Isaac Sim 中建立同名关节和相机，先加载比较层 offset，不修改真机反馈；
3. 完成单臂 replay，再完成双臂 replay；
4. 加入相机标定和接触记录后，运行同一套 `replay_metrics.py`；
5. 只有当 replay 的时间戳、关节、双臂和视觉指标都可复现，才把比较层参数整理成正式 USD/URDF 映射。

内部框架 `intern_data_engine` 的仓库版本和可复用模块已在 A-155 做过单独检查，但 OpenArm adapter/API 尚未接入本工作区。任务一只记录现有数据和对齐缺口；任务二再根据已确认的分支/commit 接入框架，不能把现有 MuJoCo `dataflow.yaml` 直接当成 Isaac Sim 配置。

#### 现有关节基线（用于 replay 对照）

`alignment/mujoco_arm_offsets.json` 中目前保存的是比较层参数，数值来源和当前限制如下：

| 类型 | 关节 | 当前值（rad） | 解释 |
|---|---|---:|---|
| 固定 offset | 右 J1/J2/J3/J4/J5/J7 | -0.000877/-0.006044/+0.000572/+0.002102/+0.001296/-0.001749 | 由稳定段平均 gap 得到，作为仿真侧比较变换。 |
| 固定 offset | 左 J1/J2/J3/J4/J7 | -0.002451/-0.002615/-0.002098/-0.001266/+0.012873 | 同上。 |
| 方向 offset | 左 J5（正/负） | -0.00670/+0.01319 | 暂按方向分组，不能合并成一个零位。 |
| 方向 offset | 左 J6（正/负） | -0.02136/+0.01579 | 暂按方向分组，需在 replay 中复验。 |
| 方向 offset | 右 J6（正/负） | -0.01283/+0.00992 | 暂按方向分组，需在 replay 中复验。 |

最近一次 `final_directional_alignment_summary.csv` 的残差仍显示 J5/J6 需要动态验证：右 J6 RMSE 约 `0.01051 rad`，左 J5 约 `0.00459 rad`，左 J6 约 `0.01534 rad`。这些值是混合方向/运动段的统计，不是接触或视觉指标；手指关节目前按既定范围不加入本轮 MuJoCo/Isaac Sim 补偿。

因此 replay 的比较顺序固定为：

```text
原始 action
  -> 关节名/顺序/单位/正方向映射
  -> 固定 offset（sim_offsets）
  -> 按运动方向选择方向 offset（sim_direction_offsets）
  -> Isaac Sim 控制器
```

方向 offset 只用于仿真侧输入/比较层。真机原始反馈文件必须保留，不能用补偿后的值覆盖，否则无法判断补偿是否有效。

### A-109：Isaac Sim 迁移用采集与 replay 方案（可填写模板）

2026-09-11：保留前面的 MuJoCo 盘点和 offset 版本，新增本方案作为 Isaac Sim 迁移的采集计划。重新采集时不删除旧 CSV、Parquet、JPEG 或旧 summary；每轮使用新的 `session_id`，并在本节填写对应路径。所有“未测量”必须明确写出，不能用仿真默认值代替真机数据。

#### 1. 本轮采集基本信息

| 字段 | 填写内容 |
|---|---|
| session_id | `____________________________` |
| 日期/时间 | `____________________________` |
| 操作员 | `____________________________` |
| 真机固件/硬件版本 | `____________________________` |
| Isaac Sim 版本 | `____________________________` |
| Isaac Lab/内部框架版本 | `____________________________` |
| 采集配置文件/commit | `____________________________` |
| 原始数据目录 | `____________________________` |
| 备注 | `____________________________` |

建议目录结构：

```text
alignment/results/isaacsim_migration/<session_id>/
  metadata.yaml
  calibration/
  objects/
  workspace/
  vision/
  bimanual/
  control/
  contact/
  trajectories/
  replay/
```

#### 2. 六类参数的现状和采集要求

| 类别 | 已有记录 | 重新采集/补齐内容 | Isaac Sim 对齐项 | 当前状态 |
|---|---|---|---|---|
| 物体 | 现有 MuJoCo session 只有 `scene: demo`，没有完整物体参数表 | 类别、尺寸、质量、质心、惯量、摩擦、刚度、颜色、纹理、抓取/插接/旋拧区域 | USD 刚体几何、质量/惯量、材质摩擦、接触刚度阻尼、任务区域 | `待补齐` |
| 工作区 | 有场景名和相机名，无可验收的桌面/夹具/障碍物尺寸表 | 桌面尺寸、容器/工装/目标位姿、固定夹具、障碍物、边界 | 世界坐标、桌面碰撞体、夹具约束、障碍物和边界 | `待补齐` |
| 视觉 | 历史 MuJoCo episode 有 5 个相机各 59 张 JPEG，但不作为当前仿真数据 | 内外参、畸变、分辨率、FPS、曝光、光照、背景、遮挡、噪声、时间戳 | Isaac 相机 pose/intrinsics、渲染分辨率/FPS、噪声/曝光/光照模型 | `需用 Isaac Sim 重新生成` |
| 双臂协同 | 有左右 action/obs Parquet，但未计算同步、交接和相对运动指标 | 左右角色、交接位姿、同步时间窗、双臂间距、相对速度、统一时钟 | 左右基座变换、同一 simulation tick、双臂控制器和交接触发 | `部分已有` |
| 控制 | 有关节静态/方向 gap；action 元数据标称 250 Hz | 控制频率、command→feedback 延迟、观测延迟、关节噪声、末端误差、夹爪误差 | 控制周期、动作保持、执行器增益/阻尼、限幅、延迟和噪声模型 | `部分已有` |
| 接触 | 当前 alignment 结果未发现力/扭矩/接触事件记录 | 接触力、摩擦、插入阻力、旋拧扭矩、碰撞/滑移阈值、事件时间 | contact sensor、接触材质、碰撞过滤、插入力/扭矩和滑移判定 | `未采集` |

#### 3. 物体和工作区填写表

每个物体单独一行；实测值、CAD 值和估计值分开填写。

| object_id | 类别/用途 | 尺寸 (m) | 质量 (kg) | 质心/惯量 | 摩擦 μ | 刚度/阻尼 | 抓取/插接/旋拧区域 | USD/URDF 路径 | 来源/误差 | 已录入 Isaac |
|---|---|---|---:|---|---:|---|---|---|---|---|
| `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `[ ]` |
| `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `[ ]` |

| workspace_id | 桌面尺寸 (m) | 容器/工装/目标位姿 | 夹具 | 障碍物 | 边界 | 坐标系/原点 | 场景文件 | 实测照片 |
|---|---|---|---|---|---|---|---|---|
| `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |

#### A-161.2：可直接运行的只读双臂记录器

已生成 [`isaacsim_capture_bimanual_metrics.py`](isaacsim_capture_bimanual_metrics.py)。它已使用当前 stage 检出的末端路径：

```text
左：/openarm_v20/Geometry/world/openarm_body_link0/.../openarm_left_ee_base_link
右：/openarm_v20/Geometry/world/openarm_body_link0/.../openarm_right_ee_base_link
```

它不发送关节命令、不修改 USD、不访问真机。它在每个 physics tick 读取左右末端世界位姿，持续 10 秒，输出新的会话目录：

```text
alignment/results/isaacsim_migration/isaac_bimanual_<时间>/bimanual/
  config.json
  sync_motion.csv
  metrics.json
```

`sync_motion.csv` 包含仿真时间、左右末端位置/四元数、`ee_distance_m` 和 `relative_speed_mps`；`metrics.json` 汇总最小/最大间距与最大/平均相对速度。该脚本没有接入 action 发布端，所以会诚实写 `action_sync: not_measured`，不能把同一 physics tick 当成控制同步测量。

操作：

1. 在 Isaac Sim 保持当前 OpenArm USD 已打开，先准备好一段约 10 秒的双臂无接触动作，时间线先不要播放。
2. 打开 **Window → Script Editor → File → Open**，选择：

   ```text
   /home/tangyuan/openarm_ws/alignment/isaacsim_capture_bimanual_metrics.py
   ```

3. 点击 **Run**。控制台出现 `OPENARM_CAPTURE_ARMED` 后才点击 **Play**；记录器不会移动机械臂。
4. 执行双臂动作。10 秒后控制台出现 `OPENARM_CAPTURE_COMPLETE` 和 `WROTE ...metrics.json`。
5. 将 `metrics.json` 的内容发回。下一步再接入同一 action 分发器，测量真正的仿真 action 同步。

如果已知交接位置，把脚本顶部的：

```python
HANDOFF_TARGET_M = None
```

替换为例如：

```python
HANDOFF_TARGET_M = (0.35, 0.00, 0.25)
```

则会额外输出 `ee_arrival_skew_s`，它是两末端进入同一位置阈值的到达时间差，只能表示到位同步代理指标。

2026-09-14 更新：当前导入 USD 未触发原先的 PhysX-step callback，导致只生成 `config.json`。记录器现改用 Isaac Sim 的 Kit frame update callback，并在 Run 后自动请求 Timeline Play；它仍然只读，不会发送关节动作。重新复制更新后的脚本到 Isaac Sim 服务端后运行一次，等待 12 秒即可生成 CSV 和 metrics。

首次 Isaac Sim 原生记录结果（`isaac_bimanual_20260914_115311`）：

| 指标 | 结果 | 结论 |
|---|---:|---|
| 记录时长 | 10.005 s | 记录器和输出路径有效。 |
| 样本数 | 583 | Kit frame 回调有效，平均约 58.3 Hz。 |
| 双臂末端距离 min/max | 0.302685 / 0.302685 m | 两臂在整段内没有相对运动。 |
| 相对速度 | 未计算 | 该 stage 的 simulation clock 没有推进；旧记录器因而不应将其当作 physics tick 数据。更新后的记录器会在时钟停滞时使用 Kit frame 时间计算速度。 |
| action 同步 | 未测量 | 当前没有 action 分发器或 action 时间戳。 |
| 交接到位时间差 | 未测量 | 未设置 `HANDOFF_TARGET_M`，且两臂没有执行交接动作。 |

该记录只验收“数据记录链路可用”，不验收双臂协同运动。下一步必须先使导入机器人在 Isaac Sim 中成为可播放、可控制的 articulation，并执行一条新的双臂动作；之后才重新运行记录器。

#### A-161.3：ROS 2 驱动 Isaac Sim 后再测量

是。要测控制频率、动作延迟、左右 action 同步、双臂间距和相对速度，需要建立如下**仅仿真**的数据路径：

```text
ROS 2 仿真命令节点
        ↓ /sim/openarm/*/joint_command
Isaac Sim ROS 2 Bridge + articulation controller
        ↓
OpenArm USD articulation
        ↓
/sim/openarm/joint_states、/sim/openarm/tf、记录器 CSV
```

此阶段不要连接真机 CAN、真机 bringup 或真实电机话题。所有 topic 使用 `/sim/openarm/` 前缀和独立 `ROS_DOMAIN_ID`，避免一次 ROS 发布误发到真机控制器。

先在运行 Isaac Sim 的主机检查 ROS 2 是否具备；这一步只读：

```bash
test -f /opt/ros/jazzy/setup.bash \
  && echo ROS_JAZZY_OK \
  || echo ROS_JAZZY_MISSING

test -x "$HOME/isaacsim-6.0.1/isaac-sim.streaming.sh" \
  && echo ISAAC_6_OK \
  || echo ISAAC_6_MISSING
```

只有输出 `ROS_JAZZY_OK` 和 `ISAAC_6_OK` 后，才以独立 ROS 域启动新的 Isaac Sim 服务端实例：

```bash
export ROS_DOMAIN_ID=42
source /opt/ros/jazzy/setup.bash
cd "$HOME/isaacsim-6.0.1"

./isaac-sim.streaming.sh \
  --/isaac/startup/ros_bridge_extension=isaacsim.ros2.bridge \
  --/exts/omni.kit.livestream.app/primaryStream/publicIp=192.168.18.72 \
  --/exts/omni.kit.livestream.app/primaryStream/signalPort=49100 \
  --/exts/omni.kit.livestream.app/primaryStream/streamPort=47998
```

启动后在 Isaac Sim 的 **Extension Manager** 搜索并启用 `isaacsim.ros2.bridge`。再为当前 articulation 建立 ROS 2 action graph：输入为 `/sim/openarm/left/joint_command`、`/sim/openarm/right/joint_command`，输出为 `/sim/openarm/joint_states` 和 `/sim/openarm/tf`。在 action graph 尚未创建、关节顺序尚未核对前，不能直接向 `/joint_states` 或任何不带 `/sim/openarm/` 前缀的控制 topic 发布。

验收顺序：

1. 使用 `ros2 topic list | grep '^/sim/openarm/'` 确认只有仿真 topic；
2. 对一个关节发布一次小幅、限位内的位置目标，确认模型移动且 `/sim/openarm/joint_states` 更新；
3. 同一进程、同一 timestamp 下向左右命令 topic 发布，记录 action 的发送时间和收到的 joint state；
4. 运行 `isaacsim_capture_bimanual_metrics.py`，生成新的 `sync_motion.csv` 和 `metrics.json`；
5. 最后才计算 action 同步、反馈延迟、最小间距与相对速度。

当前状态：尚未完成第 1 步，不能把第一条静态记录解释为 ROS 控制或双臂协同结果。

2026-09-14 主机检查结果：`ROS_JAZZY_MISSING`，`ISAAC_6_OK`。因此不在该共享主机上用 `apt` 安装 ROS 或修改系统 Python。推荐方案是：Isaac Sim 端使用其内置 `isaacsim.ros2.bridge`；外部 ROS 2 命令节点以后运行在 `ros:jazzy` Docker 容器中并使用 host network。这样 ROS 2 运行时、工作区和依赖都留在容器内，主机文件系统只保存本项目数据。Isaac Sim 6 官方支持 Ubuntu 24.04 + ROS 2 Jazzy，并要求通过 `isaacsim.ros2.bridge` 连接 ROS。先在 GUI Extension Manager 启用该 extension，再检查 Docker 可用性后创建隔离的 ROS 节点环境。

Docker 检查结果：`Docker Engine 29.1.3`，`DOCKER_OK`。下一步使用一次性 `ros:jazzy-ros-base` 容器作为仿真 ROS 终端；该容器没有 CAN、USB 或主机目录挂载。启动 Isaac Sim ROS bridge 时和容器都使用 `ROS_DOMAIN_ID=42`，将其与真机 ROS domain 隔离。

后续改为固定名称的长期容器 `openarm-sim-ros`：不要使用 `--rm`；容器用 `sleep infinity` 常驻，进入时使用 `docker exec -it openarm-sim-ros bash`。它仍然不挂载主机目录、CAN 或 USB；删除该容器只会删除容器内部的 ROS 工作状态，不会删除 OpenArm 工作区。

容器验证结果：`ros2 --help` 正常；首次 `ros2 topic list` 只有 `/parameter_events`、`/rosout`。这仅说明容器 ROS 2 正常，不能说明 Isaac Sim 已连接。下一步必须将 Isaac Sim 服务端重启到相同的 `ROS_DOMAIN_ID=42` 并启用 `isaacsim.ros2.bridge`；之后再构建 OpenArm articulation 的 action graph。

#### A-161.4：创建只读 OpenArm ROS Action Graph

默认 `/parameter_events` 和 `/rosout` 是 ROS 2 CLI 自身的默认 topic；没有 `/sim/openarm/` 说明 USD 中还没有 ROS 图。运行 [`isaacsim_create_openarm_ros_graph.py`](isaacsim_create_openarm_ros_graph.py) 会在当前 USD 创建 `/OpenArmRosBridge`，包含一个状态发布器、一个命令订阅器和 articulation controller：

```text
/sim/openarm/joint_command  (sensor_msgs/JointState，输入)
/sim/openarm/joint_states   (sensor_msgs/JointState，输出)
```

脚本本身不发布命令，因而不会移动模型。运行前确认 Isaac Sim 已以 `ROS_DOMAIN_ID=42` 启动且 `isaacsim.ros2.bridge` 已启用。然后在 Script Editor 运行：

```python
exec(compile(open("/home/tangyuan/openarm_ws/alignment/isaacsim_create_openarm_ros_graph.py", encoding="utf-8").read(), "/home/tangyuan/openarm_ws/alignment/isaacsim_create_openarm_ros_graph.py", "exec"))
```

看到 `OPENARM_ROS_GRAPH_CREATED` 后点击 Play；Docker ROS 终端执行：

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
ros2 topic list | grep '^/sim/openarm/'
ros2 topic echo --once /sim/openarm/joint_states
```

只有确认状态 topic 连续发布、关节名称和顺序正确后，才允许发布一条小幅的 `/sim/openarm/joint_command` 测试动作。

当前验收进度：Docker 端已发现 `/sim/openarm/joint_command` 和 `/sim/openarm/joint_states`，因此 ROS domain、Bridge 和 `/OpenArmRosBridge` graph 的 topic 注册已成功。`ros2 topic echo --once` 在没有新 state message 时会阻塞等待，这不表示失败；必须在 Isaac Sim 点击 Play 后再用有限时间的 echo 验证实际 state 发布。

若 `ros2 topic info -v /sim/openarm/joint_states` 显示 1 个 publisher、但 `timeout 5 ros2 topic echo --once ...` 没有任何消息，说明 graph 的 `OnPlaybackTick` 没有执行。更新后的 graph 脚本改用 `omni.graph.action.OnTick`，重新运行时只替换 `/OpenArmRosBridge`，不修改机器人 prim、关节、USD mesh 或控制命令。替换后无需依赖 timeline，也应能收到静态 `JointState`；物理运动控制仍只在明确发送仿真 command 后单独验证。

若 `OnTick` 仍注册 publisher 但没有发送 ROS message，运行 `isaacsim_ros2_joint_state_probe.py`。它用 Isaac Sim 内部 `rclpy` 每 0.2 s 向 `/sim/openarm/joint_states_probe` 发布一个仅含关节名称的 `sensor_msgs/JointState`。该探针不订阅 command、不设置关节位置、不写 USD，是 Bridge 到 Docker DDS 传输的独立验证。Docker 端用 `timeout 5 ros2 topic echo --once /sim/openarm/joint_states_probe` 检查；收到 probe 后再修复正式 Action Graph 的执行流。

探针在 Isaac Sim Console 显示 `OPENARM_ROS_PROBE_PUBLISHING`、但 Docker 仍收不到消息时，表明 Isaac 内部发布正常，失败点是 Fast DDS 的本机共享内存跨 Docker IPC namespace。长期容器必须使用 `--network host --ipc host`；重建该容器只删除容器内部 ROS 运行环境，绝不删除 OpenArm 工作区、USD、CAN 或 USB 配置。

本次实测即使加入 `--ipc host` 仍未收到 probe，因此改用强制 UDP 的 [`fastdds_udp.xml`](fastdds_udp.xml)。该配置必须在**启动前**同时传给 Isaac Sim 和 Docker ROS 进程：`FASTRTPS_DEFAULT_PROFILES_FILE`。这一步不重启主机；只保存当前 USD、停止当前 kit 服务进程、重建 `openarm-sim-ros` 容器并启动新的 Isaac Sim 服务。完成后重新打开 `openarm_v20_isaac_ros.usda`，运行 `isaacsim_ros2_joint_state_probe.py`，再用 Docker echo 验证。

UDP profile 不是 USD 属性，因而不会随 `openarm_v20_isaac_ros.usda` 保存；它必须在启动 Isaac Sim 的 shell 环境中存在。固定使用 [`start_isaacsim_ros_udp.sh`](start_isaacsim_ros_udp.sh) 启动服务端：该脚本设置 `ROS_DOMAIN_ID=42`、`RMW_IMPLEMENTATION=rmw_fastrtps_cpp` 和 `FASTRTPS_DEFAULT_PROFILES_FILE`，然后启用 `isaacsim.ros2.bridge`。服务端重新启动后，仍需打开保存的 ROS USD，并重新运行内存态的 `isaacsim_ros2_joint_state_probe.py`；probe publisher 不会存入 USD，因此 Docker 报“topic does not appear to be published yet”是此时的预期状态。

若启用 UDP/ROS Bridge 的服务端出现 WebRTC 黑屏，优先恢复已验证的原始无 ROS Bridge 流式启动方式，确认显示链路稳定后再单独排查 DDS。恢复只结束当前 `kit` 服务进程并启动新的无 ROS 实例；不重启主机、不删除 Docker、USD、采集结果或配置文件。

2026-09-14 WebRTC 黑屏根因：服务端端口检查同时显示两个 `kit` PID（`3579492`、`3573727`）。原始流式日志出现 `NVST_R_INVALID_STATE Cannot transition from current state`，客户端日志依次出现 `Stream started ... success` 和 `Stream stopped ... error`。这表明同一流式状态被多个 Isaac Sim 实例竞争；与 GPU、ROS topic 或 USD 无关。修复方式是仅结束这两个已确认的 `kit` PID，确认 `49100` 和 `47998` 均无监听，再等待一个新实例完全启动后才连接 WebRTC Client。

2026-09-14 ROS 2 UDP 探针验收通过：Docker 容器收到 `/sim/openarm/joint_states_probe` 的 `sensor_msgs/JointState`。消息含左右各 7 个关节及各 2 个手指，共 18 个正确关节名；`position`、`velocity`、`effort` 为空是 probe 的预期设计。该结果证明 `ROS_DOMAIN_ID=42`、Fast DDS UDP profile、Isaac 内部 `rclpy`、Docker ROS Jazzy 和 host-network 数据通路均已连通。它不证明正式 Action Graph 的状态发布或关节控制已通过；下一项是读取 articulation 实际位置并发布到正式 `/sim/openarm/joint_states`。

实际状态发布器：运行 [`isaacsim_publish_openarm_joint_state.py`](isaacsim_publish_openarm_joint_state.py)。它在 Script Editor 内初始化当前 OpenArm articulation、读取 `dof_names`、`get_joint_positions()` 和 `get_joint_velocities()`，以最高 60 Hz 发布 `/sim/openarm/joint_states`。脚本不创建 command subscriber、不调用 `apply_action` 或任何 `set_joint_*` 方法；只调用 Timeline Play 让 PhysX 初始化句柄。Docker 验收要求 `JointState.name`、`position` 数组长度相同，且 18 个关节名称与 probe 一致。通过前不发送仿真关节命令。

2026-09-14 正式状态发布验收通过：Docker 从 `/sim/openarm/joint_states` 收到 18 个 `name`、18 个 `position` 和 18 个 `velocity`。当前 articulation 输出顺序为左右臂 J1--J7 交替，随后是左手指 2 个、右手指 2 个；后续所有 action、状态 CSV 和 replay 文件必须保存 `joint_names` 列或同名数组，不能假定“左臂全在前、右臂全在后”。`effort` 当前为空，不能拿它作为接触力或扭矩数据。

当前可开始填表的 Isaac-native 项目：控制状态采样频率、静止位置/速度噪声、关节顺序、双臂当前间距和静态相对速度。尚未可填的项目：command→feedback 延迟、动作频率、双臂 action 同步、交接窗口、末端轨迹和接触指标；这些必须在下一步创建带时间戳的仿真命令发布器后测量。

#### 3.1 ROS 状态静止基线（现在执行，不发送命令）

正式 state 已通过后，先用 30 秒原始 rosbag 计算 `state_frequency_hz`、每一关节的 `position_std_rad` 和 `velocity_std_rad_s`。该步骤只订阅 `/sim/openarm/joint_states`；不向 command topic 发布，因而不会改变仿真姿态，更不会接触真机。

在**新主机**的普通终端运行。容器内先写入 `/tmp`，随后复制到工作区 session；不要改动正在运行的 Isaac Sim 终端。

```bash
SESSION_ID="isaacsim_$(date +%Y%m%d_%H%M%S)"
SESSION="$HOME/openarm_ws/alignment/results/isaacsim_migration/$SESSION_ID"
mkdir -p "$SESSION/control" "$SESSION/bimanual"
echo "SESSION=$SESSION"

docker exec -e SESSION_ID="$SESSION_ID" -i openarm-sim-ros bash -lc '
  source /opt/ros/jazzy/setup.bash
  export ROS_DOMAIN_ID=42
  export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
  export FASTRTPS_DEFAULT_PROFILES_FILE=/opt/openarm/fastdds_udp.xml
  timeout -s INT 30s ros2 bag record \
    -o "/tmp/${SESSION_ID}/idle_30s" \
    /sim/openarm/joint_states
'

docker cp "openarm-sim-ros:/tmp/$SESSION_ID/idle_30s" "$SESSION/control/idle_30s"
find "$SESSION/control/idle_30s" -maxdepth 2 -type f -printf '%P %s bytes\n'
```

验收时必须至少有 `metadata.yaml` 和 `*.db3` 或 `*.mcap`；这份 bag 的 source 是 `isaac_sim`。分析文件须逐条保留消息 header 时间、完整 `name` 数组和同序的 `position`/`velocity`，然后按关节名统计，不能按固定数组下标统计。

本段完成后记录：

| 参数 | source | 原始证据 | 当前状态 |
|---|---|---|---|
| `state_frequency_hz` | `isaac_sim` | `control/idle_30s` | 待由 header 时间差计算 |
| `position_std_rad` | `isaac_sim` | `control/idle_30s` | 待按 `joint_name` 统计 |
| `velocity_std_rad_s` | `isaac_sim` | `control/idle_30s` | 待按 `joint_name` 统计 |
| `joint_order` | `isaac_sim` | `control/idle_30s` | 已确认：左右 J1--J7 交替，后接左右各两个手指 |
| `effort` | `not_available` | `/sim/openarm/joint_states` | 当前发布器未提供 effort |

只有静止 bag 复制完成后，才创建带单调时间戳的仿真 command publisher，测量 action 同步、command→state 延迟、双臂间距、相对速度及交接窗口。

静止 bag 已成功录制时，用 [`analyze_ros2_joint_state_bag.py`](analyze_ros2_joint_state_bag.py) 分析。该脚本只读取 MCAP；不发布 ROS 消息、不修改 USD、不控制 articulation。把 session ID 替换为本轮实际值：

```bash
SESSION_ID="isaacsim_20260914_145911"
SESSION="$HOME/openarm_ws/alignment/results/isaacsim_migration/$SESSION_ID"

docker cp "$SESSION/control/idle_30s" "openarm-sim-ros:/tmp/$SESSION_ID/"
docker cp "$HOME/openarm_ws/alignment/analyze_ros2_joint_state_bag.py" \
  "openarm-sim-ros:/tmp/analyze_ros2_joint_state_bag.py"

docker exec -i openarm-sim-ros bash -lc "
  source /opt/ros/jazzy/setup.bash
  python3 /tmp/analyze_ros2_joint_state_bag.py \\
    /tmp/$SESSION_ID/idle_30s \\
    --output /tmp/$SESSION_ID/idle_metrics
"

docker cp "openarm-sim-ros:/tmp/$SESSION_ID/idle_metrics" "$SESSION/control/idle_metrics"
cat "$SESSION/control/idle_metrics/metrics.json"
```

2026-09-14 session `isaacsim_20260914_145911` 已完成原始静止基线录制：`control/idle_30s/idle_30s_0.mcap`（830487 bytes）及 `metadata.yaml`（1300 bytes）已由 Docker 复制到工作区。分析结果尚待生成；在 `metrics.json` 落盘前，不填写频率或噪声数值。

2026-09-14 session `isaacsim_20260914_145911` 的 `control/idle_metrics/metrics.json` 已生成：945 条 `/sim/openarm/joint_states`，18 个关节均有 position/velocity；基于相邻 header 的瞬时频率均值为 `35.3769 Hz`、标准差 `12.1783 Hz`、范围 `19.3953--60.0844 Hz`。按约 29.75 s 的 recorder 有效录制区间计算，平均消息吞吐约 `31.8 Hz`。这两个数值是**当前状态发布频率**，不是最终控制频率。

这段“静止”采集不满足静止噪声验收条件，不能将其标准差写为噪声参数：左 J5 `position_std=0.108207 rad`、左 J6 `velocity_std=0.339713 rad/s`、左 J7 `velocity_std=0.425868 rad/s`；右 J5 `position_std=0.040970 rad`、右 J6 `velocity_std=0.245891 rad/s`、右 J7 `velocity_std=0.221322 rad/s`。这些幅度远高于数值抖动，表明在没有 command 的情况下 articulation 仍在 PhysX 中下落、回弹或从导入初值收敛。此 bag 归档为 `source=isaac_sim, trial=uncommanded_dynamics`，可用于检查被动动力学，但 `sim_static_position_noise` 和 `sim_static_velocity_noise` 均保持 `not_valid`。

当前已确认的状态顺序为：`left_J1,right_J1,...,left_J7,right_J7,left_finger_1,left_finger_2,right_finger_1,right_finger_2`。`effort` 未发布，标记 `not_available`。下一轮静止基线前，必须显式设置初始关节姿态并给每个关节设置保持目标/执行器参数，等待稳定后再录制；不能从本轮自由动态样本推断仿真噪声，也不能用于真机噪声。

为获得有效的 Isaac 静止基线，运行 [`isaacsim_hold_openarm_position.py`](isaacsim_hold_openarm_position.py)。它在 PhysX 初始化后读取一次当前 18-DoF 位置，并在每个 Kit update 向 Isaac articulation controller 重复应用相同 position target。它没有 ROS publisher、ROS subscriber 或 command topic，也不连接真机。Console 出现 `OPENARM_STATIC_HOLD_ACTIVE dofs=18` 后，等待 5 s 让瞬态衰减，再按 3.1 节新建 session 录制 30 s `idle_30s`。该轮记录的 `action_hold_mode` 写作 `simulator_position_target_each_update`；若结果仍出现显著漂移，不能把它标记为噪声，须检查 USD drive stiffness/damping 或关节约束。

Isaac Sim 6 的 `isaacsim.core.prims.Articulation` 没有旧接口 `get_articulation_controller()`；position-hold 实现必须直接使用 `articulation.apply_action(ArticulationAction(...))`。若 Console 出现该 AttributeError，只需将 `state["controller"] = state["arm"].get_articulation_controller()` 替换为 `state["controller"] = state["arm"]`，然后重新运行；这不是 ROS、DDS 或模型路径问题。

2026-09-14 session `isaacsim_hold_20260914_151105` 已验证 simulator-only position hold：1185 条状态，18 个关节都有 position/velocity，瞬时 state 发布频率均值 `41.8589 Hz`（范围 `18.7032--59.6639 Hz`）。相对于无 command 自由动态段，保持效果明显：左 J5 position std 从 `0.108207` 降至 `0.001099 rad`，右 J5 从 `0.040970` 降至 `0.000791 rad`。但整个 bag 仍含开始时的短暂收敛：左 J6/J7 position std 分别为 `0.004235/0.005700 rad`，且位置范围分别达 `0.04862/0.06691 rad`。因此本轮标记 `sim_position_hold_settling`, 不作为最终 `sim_static_*_noise`。保持订阅不应重跑或重启；持续 hold 至少 10 s 后，以新 `SESSION_ID` 再录制 30 s，并将这一轮作为候选静止噪声基线。

2026-09-14 session `isaacsim_hold_stable_20260914_151311` 通过有效的 Isaac position-hold 静止基线验收：`control/idle_30s` 含 1190 条 `/sim/openarm/joint_states`，有效录制时间约 29.76 s，平均消息吞吐约 `40.0 Hz`；相邻 header 的瞬时频率均值 `41.9969 Hz`、标准差 `9.2041 Hz`、范围 `31.5170--53.9818 Hz`。18 个关节的 `position_std_rad=0.0`、`velocity_std_rad_s=0.0`，每个 velocity 均为零。这是 `action_hold_mode=simulator_position_target_each_update` 下的确定性仿真基线，记录为：

| 参数 | 数值 | source | 证据 | 结论 |
|---|---:|---|---|---|
| `sim_state_mean_throughput_hz` | `40.0` Hz | `isaac_sim` | `control/idle_30s` | 当前 ROS 状态实际平均吞吐，不等同真机控制频率 |
| `sim_state_instantaneous_hz_mean` | `41.9969` Hz | `isaac_sim` | `control/idle_metrics/metrics.json` | 受流式/Kit 调度影响，存在频率抖动 |
| `sim_static_position_std_rad_max` | `0.0` rad | `isaac_sim` | 同上 | hard position-hold 的数值结果 |
| `sim_static_velocity_std_rad_s_max` | `0.0` rad/s | `isaac_sim` | 同上 | hard position-hold 的数值结果 |
| `real_static_position_noise` | `not_available` | `real` | 无真机上电采集 | 不能以仿真零值替代 |
| `real_static_velocity_noise` | `not_available` | `real` | 无真机上电采集 | 不能以仿真零值替代 |
| `effort/contact` | `not_available` | `isaac_sim` | state message effort=[] | 不能用于接触或力矩对齐 |

此轮确定了静止控制基线和 joint order；下一项是对同一 position-hold 下的双臂末端距离/相对速度记录，再创建带单调时间戳的小幅仿真 command 轨迹测 action 同步与 command→state 延迟。

2026-09-14 双臂几何 recorder 已产出 `isaac_bimanual_static_20260914_154430/bimanual/metrics.json`：447 samples，左右角色暂记 `giver/receiver`，末端距离范围 `0.3009149834--0.3126449049 m`，相对速度均值/最大值 `0.0077246/0.0467293 m/s`。本 recorder 与 position-hold 启动在同一时刻，距离跨度为 `0.0117299 m`，故该段包含 hold 初始化的末端收敛，而不是有效的静止间距/相对速度。归档为 `source=isaac_sim, trial=hold_start_transient`；不得填写为静态相对速度、最小安全距离或交接窗口。保持脚本继续运行至少 10 s 后，重新录制仅含稳定 hold 的 10 s 末端段；只有该段距离基本恒定、相对速度接近零时，才能填写名义静态间距。

2026-09-14 session `isaac_bimanual_20260914_155625` 通过双臂稳定 hold 的名义静态间距验收：601 samples、`10.0011 s`，`ee_distance_m.min=max=0.3121815343 m`。可填写 `sim_static_ee_distance_m=0.3121815343`，source=`isaac_sim`、mode=`static_position_hold`。该 recorder 的 `relative_speed_mps` 为 `null`，原因是导入 USD 的 simulation clock 没有推进，速度计算器没有产生有效 dt；字段应写 `not_measured`，不能由“距离恒定”改填为 `0 m/s`。同样，未发送任何 action，故 `action_sync`、左右到达时间、到达偏差和 `handoff_window` 均为 `not_measured/not_configured`。下一项需要一个带 header 时间戳的仿真 command publisher 加正式 command subscriber，完成后才测相对速度、action 同步和 command→state 延迟。

#### 3.2 带时间戳的仿真 command 测试

动态测量使用独立的 [`isaacsim_timestamped_command_bridge.py`](isaacsim_timestamped_command_bridge.py)，不使用 `/sim/openarm/joint_command`，而是：

```text
/sim/openarm/timestamped_joint_command  input JointState
/sim/openarm/command_receipt             output JointState（接收/应用时刻）
/sim/openarm/joint_states                output JointState（关节反馈）
```

它停用仅 Script Editor 内的旧 position-hold/state callbacks，再向 Isaac articulation 直接应用收到的关节 target；不访问 CAN、USB、真机 controller 或默认 command topic。第一条测试仅为两臂 J1 的绝对 position target：left `-0.0328544522 rad`、right `0.0331392907 rad`，即已验证稳定姿态各变化 `0.02 rad`。发布脚本是 [`publish_timestamped_bimanual_test.py`](publish_timestamped_bimanual_test.py)，必须先在 Docker 录制 command、receipt 和 state 原始 bag，再发布一次。

执行 `ros2 topic pub` 前必须在**同一终端、同一 shell**先执行 `SEC=$(date +%s)` 和 `NSEC=$(date +%N)`；若两变量为空，YAML 中 `header.stamp.sec/nanosec` 会解析成 `None`，报 `Value 'None' is expected to be a dictionary but is a NoneType`，且不会发布任何 command。命令结尾只能是单独的 `'`，不可附加 `~`、反斜杠或其他字符。

2026-09-14 timestamped command publisher 已成功发送一条 simulator-only `JointState`：header stamp `1789373294.509100741`，topic `/sim/openarm/timestamped_joint_command`，targets `openarm_left_joint1=-0.0328544522 rad`、`openarm_right_joint1=0.0331392907 rad`。该输出只证明 Docker publisher 成功序列化并发布；需在 Isaac Console 看到 `COMMAND_RECEIVED` 和 `COMMAND_APPLIED`，且在 rosbag 中同时有 command、`command_receipt`、state 三个 topic 后，才能确认 command bridge 及开始计算延迟。

同轮 Console 已出现 `COMMAND_RECEIVED ['openarm_left_joint1', 'openarm_right_joint1']`，证明 Docker→Isaac 的 command subscriber 可达。随后 `BRIDGE_WAITING TypeError('only length-1 arrays can be converted to Python scalars')` 是状态 publisher 将 Isaac Sim 返回的二维 `(1,18)` joint array 当作一维 array 转换导致；这轮不能计算反馈延迟，需以 flatten 后的 bridge 重跑。终端 B 中 `$SESSION` 未定义，`docker cp "$SESSION/control/..."` 因而展开到 `/control/...` 并失败；session 环境变量仅存在创建它的终端 A。后续复制必须在终端 A 完成，或在终端 B 明确重新赋值 `SESSION_ID` 和 `SESSION`。两项均为脚本/终端作用域问题，不涉及 CAN、USB 或真机。

2026-09-14 dynamic session `isaacsim_dynamic_20260914_161627` 的原始 bag 已复制到工作区：`control/dynamic_test/dynamic_test_0.mcap`（417840 bytes）和 `metadata.yaml`（2069 bytes）。复制成功不等同延迟验收通过；下一步用 `ros2 bag info` 检查 `/sim/openarm/timestamped_joint_command`、`/sim/openarm/command_receipt` 和 `/sim/openarm/joint_states` 的消息数，三者必须都非零。

验收结果：该 bag 时段为 `08:16:28.014--08:16:39.735`，仅含 `/sim/openarm/joint_states` 470 条和已注册但为零的 `/sim/openarm/command_receipt`；没有 command topic。此前成功发布的 command header 为 `08:08:14`，不在 bag 时段内。因此该 session 标记 `dynamic_state_only_invalid_for_latency`，不计算 command→receipt、command→feedback 或左右同步。重测必须先启动 recorder、等待它订阅 state；随后在录制窗口内创建 command publisher、等待 DDS discovery 2 s、发送一次命令并保留 publisher 2 s。

第二次重测 session `isaacsim_dynamic_ok_20260914_161929` 的 MCAP 为 0 messages（两个已注册 topic 均为 0），因此其 `2262-04-11` start/end 为 MCAP 空包占位值，不是 ROS 时钟或主机时间错误。该结果表明 recorder 期间没有收到 state publisher，必须先重新运行修正后的 timestamped bridge、在 Docker 用 `ros2 topic echo --once /sim/openarm/joint_states` 验证连续 state，再开始下一次 recorder；本空包不用于任何动态指标。

后续排查发现 `/sim/openarm/joint_states` 同时有两个 publisher：遗留 `openarm_isaac_actual_joint_state` 与当前 `openarm_isaac_timestamped_command_bridge`。重跑脚本时仅把旧 callback 句柄设为 `None` 不会销毁 ROS node，因此旧 publisher 仍注册，可能使录包出现重复/交错状态。Isaac Script Editor 中只销毁旧 actual-state node，保留正在工作的 timestamped bridge：

```python
import builtins
old = getattr(builtins, "_openarm_actual_state_publisher", None)
if old:
    sub = old.get("subscription")
    if sub is not None:
        try: sub.unsubscribe()
        except Exception: pass
    old["subscription"] = None
    node = old.get("node")
    if node is not None:
        node.destroy_node()
    builtins._openarm_actual_state_publisher = None
    print("OLD_ACTUAL_STATE_PUBLISHER_DESTROYED")
```

Docker `ros2 topic info -v /sim/openarm/joint_states` 应显示 `Publisher count: 1` 且节点为 timestamped bridge；随后 `ros2 topic echo --once` 必须收到非空 18 项 state。不要销毁 bridge node 或重启 Kit；确认单 publisher 后再录制 command/receipt/state。

Session `isaacsim_dynamic_ok_20260914_162347` 实际 `ros2 bag info` 显示只有 command 1 条，`/sim/openarm/command_receipt=0`、`/sim/openarm/joint_states=0`。因此只能确认 command 被 recorder 看到，尚不能确认 Isaac bridge 收到/应用；该 bag 标记 `command_only_unacknowledged`，不计算延迟或动作同步。下一步先检查 topic info 和实时 state，再发任何新命令。

随后的 topic 检查确认 state 与 receipt 都只有一个 timestamped bridge publisher，但在执行 `ros2 topic info -v` 时 state publisher 的 subscription count 为 0，紧接着 `echo --once` 未显示消息。这证明 ROS endpoint 已创建，不能证明 update callback 正在成功 publish。下一诊断项是 `ros2 topic info -v /sim/openarm/timestamped_joint_command` 确认 bridge subscription endpoint，再检查 Isaac Script Editor 的最新 callback exception；在这两项确认前不继续 command 测试。

已确认 `/sim/openarm/timestamped_joint_command` 有一个 `openarm_isaac_timestamped_command_bridge` subscription endpoint，QoS reliable/volatile，与 Docker publisher 兼容。该结果证明 command subscription 已发现；仍需 state echo 与 Isaac callback log 才能证明数据流和仿真动作。

注意：重启 Isaac Sim 服务端后不会自动恢复当前打开的 USD。若 graph 脚本报 `Articulation root not found: /openarm_v20/...`，表示当前是空 stage 或打开了其他 stage；先通过 **File → Open** 重新加载：

```text
/home/tangyuan/openarm_ws/alignment/isaacsim_assets/openarm_v20_urdf/openarm_v20_isaac/openarm_v20_isaac.usda
```

确认 Stage 面板中出现 `/openarm_v20` 后，再运行 graph 脚本。不要在空 stage 上创建 ROS graph。

#### 4. 视觉采集表

真机和 Isaac Sim 使用相同 `camera_id`。原图、标定文件和每帧时间戳必须一起保存。

| camera_id | 位置/视角 | 分辨率 | FPS | 内参文件 | 外参文件 | 畸变 | 光照/曝光 | 背景/遮挡 | 噪声模型 | 真机路径 | Isaac 路径 |
|---|---|---|---:|---|---|---|---|---|---|---|---|
| `ceiling` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |
| `head_left` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |
| `head_right` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |
| `wrist_left` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |
| `wrist_right` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |

视觉采集场景至少包含：空场景、标准物体、遮挡、低/高曝光、不同光照各一段。每段填写：

| vision_trial_id | 场景 | 起止时间 | 图像帧数 | 丢帧数 | 时间戳文件 | 真机/仿真 | 备注 |
|---|---|---|---:|---:|---|---|---|
| `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |

#### 5. 双臂协同采集表

每个双臂 episode 必须同时记录左右 action、左右 observation、左右末端 TF 和统一时钟。不要只记录两条没有共同时间基准的 CSV。

| episode_id | 左臂角色 | 右臂角色 | 交接位置/姿态 | 同步窗口目标 (ms) | 实测同步 p50/p95 (ms) | 双臂最小间距 (m) | 相对速度范围 (m/s) | 交接事件时间 | 数据路径 |
|---|---|---|---|---:|---:|---:|---|---|---|
| `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |

需要从 replay 结果计算：

```text
sync_error(t)       = t_left_action(t) - t_right_action(t)
relative_pose(t)    = T_base_left_to_base_right(t)
arm_distance(t)     = ||p_left(t) - p_right(t)||
relative_speed(t)   = ||v_left(t) - v_right(t)||
handoff_window      = [交接开始时间, 交接结束时间]
```

#### 6. 控制采集表

命令、仿真状态、真机反馈和末端 TF 使用同一单调时钟字段；墙上时间只能用于人工查看。

| trial_id | 控制频率 (Hz) | action 保持方式 | command→feedback p50/p95 (ms) | observation 延迟 p50/p95 (ms) | 关节噪声 std (rad) | 末端位置误差 (m) | 末端姿态误差 (rad) | 夹爪误差 (rad) | 数据路径 |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |

关节 gap 的固定项和方向项沿用上一节“现有关节基线”的比较层文件；新采集只在确认残差变化后更新版本，不覆盖原始反馈。

#### 7. 接触采集表

| contact_trial_id | 物体/工装 | 接触类型 | 法向力范围 (N) | 摩擦/切向力 | 插入阻力 (N) | 旋拧扭矩 (Nm) | 碰撞阈值 | 滑移阈值 | 事件时间戳 | 真机传感器/代理信号 | Isaac 传感器 |
|---|---|---|---:|---|---:|---:|---|---|---|---|---|
| `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |

#### 8. Isaac Sim 对齐检查单

每项完成后填写证据文件和结论；“完成”必须能由文件复核。

| 检查项 | 完成 | 证据文件/命令 | 结论/残差 |
|---|---|---|---|
| 关节名称、顺序、单位一致 | `[ ]` | `________________` | `________________` |
| 左右臂正方向和限位一致 | `[ ]` | `________________` | `________________` |
| 固定 offset 已加载到比较层 | `[ ]` | `________________` | `________________` |
| J5/J6 按运动方向选择 offset/迟滞 | `[ ]` | `________________` | `________________` |
| 控制周期和动作保持一致 | `[ ]` | `________________` | `________________` |
| command/observation 延迟模型一致 | `[ ]` | `________________` | `________________` |
| 左右基座位姿和同步时钟一致 | `[ ]` | `________________` | `________________` |
| 相机内外参、分辨率、FPS 一致 | `[ ]` | `________________` | `________________` |
| 光照、曝光、背景、遮挡和噪声已建模 | `[ ]` | `________________` | `________________` |
| 物体质量、质心、惯量、摩擦已录入 | `[ ]` | `________________` | `________________` |
| 工作区、夹具、障碍物碰撞体一致 | `[ ]` | `________________` | `________________` |
| 接触/插入/旋拧/滑移模型有证据 | `[ ]` | `________________` | `________________` |

#### 9. 轨迹 replay 验证记录

replay 分三层进行，上一层没有通过时不进入下一层：

1. **输入层**：Parquet/CSV 能完整读取，左右 action 行数、时间戳、关节顺序和 `qpos` 维度正确；
2. **运动层**：Isaac Sim 能按原始时间戳执行单臂和双臂 action，输出 `/sim/joint_states`、TF 和相机帧；
3. **任务层**：在相同物体/工作区下检查交接、插入、旋拧或抓取结果，并比较接触事件。

| replay_id | 输入 episode | Isaac 场景 | offset 文件 | 单/双臂 | 相机 | 接触 | 输出目录 | 结论 |
|---|---|---|---|---|---|---|---|---|
| `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |

每次 replay 必须保存：

```text
replay_metadata.yaml
action_used.parquet
sim_joint_states.parquet
sim_tf.parquet
camera_frames/ + camera_timestamps.csv
contacts.parquet（没有传感器时写明 not_available）
metrics.json
```

| 指标 | 结果 | 目标/阈值 | 通过 |
|---|---:|---:|---|
| action 时间戳完整率 | `________` | `________` | `[ ]` |
| 左右 action 同步 p50/p95 (ms) | `________` | 先记录分布；目标 `________` | `[ ]` |
| 关节 RMSE（逐关节） | `________` | 沿用对应静态/方向基线 | `[ ]` |
| 关节最大误差（逐关节） | `________` | `________` | `[ ]` |
| command→feedback 延迟 p50/p95 | `________` | `________` | `[ ]` |
| 相机 FPS/时间戳抖动 | `________` | `________` | `[ ]` |
| 视觉配对差异 | `________` | `________` | `[ ]` |
| 接触事件时间差/力误差 | `________` | `________` | `[ ]` |
| 任务结果（抓取/交接/插入/旋拧） | `________` | `________` | `[ ]` |

#### 10. 推荐执行顺序

1. 先采一条短的**单臂、无接触、固定目标**轨迹，完成关节映射、控制频率和时间戳验证；
2. 再采左右同时动作，计算同步误差、相对位姿和相对速度；
3. 加入五路相机和标定板，验证视觉帧与关节帧是否同一时间基准；
4. 加入物体、夹具和工作区参数，进行抓取/交接 replay；
5. 最后采接触、插入和旋拧数据，校准接触模型；
6. 完成独立 replay 后，才决定是否把比较层 offset 正式写入 Isaac Sim 的 USD/URDF 映射。

当前阶段的最低交付物是：一条新的真实双臂 episode、五路配对相机数据、统一时间戳、控制/观测延迟统计，以及一条能在 Isaac Sim 中重复执行的 replay 记录。

### A-110：未采集项快速补齐执行单

2026-09-11：本节用于当前这轮快速采集。先采集不改变机器人模型的原始数据，再迁移到 Isaac Sim。每次执行前复制一份本节，填写实际路径和结果；不要覆盖 A-107/A-109 的历史记录。

#### A. 创建本轮目录和元数据

~~~bash
cd ~/openarm_ws
SESSION_ID="isaacsim_$(date +%Y%m%d_%H%M%S)"
SESSION="alignment/results/isaacsim_migration/${SESSION_ID}"
mkdir -p "$SESSION"/{calibration,objects,workspace,vision,bimanual,control,contact,trajectories,replay}
cat > "$SESSION/metadata.yaml" <<'YAML'
session_id: "填写"
datetime: "填写"
operator: "填写"
robot: "OpenArm 2.0"
firmware: "填写"
hardware: "填写"
ros_distro: "jazzy"
isaac_sim_version: "填写"
isaac_lab_version: "填写"
source_commit: "填写"
notes: "填写"
YAML
echo "$SESSION"
~~~

填写结果：

~~~text
session_id: ____________________________
目录:       ____________________________
配置/commit: ____________________________
~~~

#### B. 30 秒静止基线（控制、噪声、时间戳）

该段不发送控制命令，只记录真机反馈、TF 和已存在的相机话题。先确认真实话题名：

~~~bash
source /opt/ros/jazzy/setup.bash
source ~/openarm_ws/install/setup.bash
ros2 topic list | tee "$SESSION/control/topic_list.txt"
ros2 topic list | grep -E 'joint_states|/tf|image|camera_info|command|wrench|force|torque|effort' \
  | tee "$SESSION/control/relevant_topics.txt"
~~~

确认话题后执行静止记录。将控制话题替换为现场实际名称，不存在的项不要填写：

~~~bash
timeout -s INT 30s ros2 bag record \
  -o "$SESSION/control/idle_30s" \
  /joint_states /tf /tf_static \
  /left_forward_position_controller/commands \
  /right_forward_position_controller/commands \
  /left_gripper_forward_position_controller/commands \
  /right_gripper_forward_position_controller/commands
~~~

填写结果：

~~~text
实际控制频率: __________________ Hz
静止段起止时间: __________________
joint_states 是否持续: [ ] 是  [ ] 否
静止噪声 std（左/右最大值）: __________________ rad
bag 路径: __________________
~~~

#### C. 双臂同步短轨迹（不接触物体）

在安全工作区内执行一条约 10--20 秒、左右臂同时有动作但不接触物体的轨迹。记录左右 action、左右 joint_states、TF 和夹爪命令，原始动作文件另存一份。

~~~bash
timeout -s INT 20s ros2 bag record \
  -o "$SESSION/bimanual/sync_motion_20s" \
  /joint_states /tf /tf_static \
  /left_forward_position_controller/commands \
  /right_forward_position_controller/commands \
  /left_gripper_forward_position_controller/commands \
  /right_gripper_forward_position_controller/commands
~~~

填写结果：

~~~text
episode_id: ____________________________
左臂角色: __________________  右臂角色: __________________
动作起止时间: __________________________
交接/协同动作: __________________________
左右 action 是否共用时钟: [ ] 是  [ ] 否
bag 路径: ______________________________
~~~

说明：如果 command 消息没有发送时间戳，只能得到录包接收时间的近似延迟；要测真实 command→feedback 延迟，需要在发布端加入单调时钟字段或增加时间戳 relay，并把 relay 的代码/commit 填入 metadata.yaml。

#### D. 视觉快速补齐

先记录每个相机的 CameraInfo，再记录空场景、标准物体、遮挡和曝光变化四个短片段。相机话题以 B 步骤生成的 relevant_topics.txt 为准。

~~~bash
# 对每个实际存在的 camera_info 话题执行一次
ros2 topic echo --once /camera/color/camera_info \
  > "$SESSION/calibration/camera_info_<camera_id>.yaml"

# 将现场确认过的 image 和 camera_info 话题写入此处
timeout -s INT 60s ros2 bag record \
  -o "$SESSION/vision/vision_trials_60s" \
  <image_topic_1> <camera_info_topic_1> \
  <image_topic_2> <camera_info_topic_2>
~~~

| vision_trial_id | 场景 | 相机话题 | 起止时间 | 帧数 | 丢帧数 | 曝光/光照 | bag/原图路径 |
|---|---|---|---|---:|---:|---|---|
| ________ | 空场景 | ________ | ________ | ________ | ________ | ________ | ________ |
| ________ | 标准物体 | ________ | ________ | ________ | ________ | ________ | ________ |
| ________ | 遮挡 | ________ | ________ | ________ | ________ | ________ | ________ |
| ________ | 低/高曝光 | ________ | ________ | ________ | ________ | ________ | ________ |

#### E. 物体和工作区立即登记

这一部分不需要等待 Isaac Sim。用卡尺、秤、CAD 和照片建立事实记录，后续再转换为 USD 属性。

~~~text
object_id: ____________________________
类别/用途: ____________________________
尺寸（长×宽×高 m）: __________________
质量 kg: ______________________________
质心/惯量: ____________________________
摩擦 μ（来源）: _______________________
抓取/插接/旋拧区域: ___________________
实测照片: _____________________________

workspace_id: _________________________
桌面尺寸: _____________________________
容器/工装/目标位姿: ___________________
夹具/障碍物/边界: _____________________
坐标系和原点: _________________________
场景照片/CAD: _________________________
~~~

#### F. 接触数据先确认是否可用

~~~bash
ros2 topic list | grep -Ei 'wrench|force|torque|effort|contact|ft|gripper'
~~~

若有真实力/扭矩话题，记录一次无接触基线和一次低速接触；若没有，明确填写 not_available，不要用仿真接触值冒充真机传感器。

~~~bash
timeout -s INT 30s ros2 bag record \
  -o "$SESSION/contact/contact_baseline_30s" \
  /joint_states <wrench_or_effort_topic>
~~~

~~~text
传感器/代理信号: ______________________
无接触基线: ____________________________
接触类型: ______________________________
法向力/扭矩范围: _______________________
插入阻力/滑移阈值: _____________________
数据路径或 not_available: ______________
~~~

#### G. 当前轮次完成判定

| 项目 | 已完成 | 证据路径 | 备注 |
|---|---|---|---|
| session metadata | [ ] | ________ | ________ |
| 30 秒静止控制基线 | [ ] | ________ | ________ |
| 双臂同步短轨迹 | [ ] | ________ | ________ |
| 相机内参/外参和帧记录 | [ ] | ________ | ________ |
| 物体/工作区参数 | [ ] | ________ | ________ |
| 接触传感器确认 | [ ] | ________ | ________ |
| 原始数据只读备份 | [ ] | ________ | ________ |

完成 B--F 后，再把同一个 session_id 的 action、observation、camera 和 bag 转换为 Isaac Sim replay 输入。没有完成统一时间戳和话题核对前，不开始任务级 replay，也不修改正式 USD/URDF 映射。

当前自动化终端无法直接连接本机 ROS 2 daemon（`ros2 topic list` 会因 daemon socket 权限返回 `Operation not permitted`），所以本节命令需要在你正在运行真机 bringup 的终端执行；执行结果再填回本节，不能把未运行命令当成已采集数据。

### A-113：Isaac Sim 启动前占用检查

2026-09-11：在启动 Isaac Sim 前检查了主机进程、GPU 和采集器状态。检查命令使用主机环境执行，结果如下。

| 项目 | 检查结果 | 说明 |
|---|---|---|
| GPU | RTX 5090，显存约 10397/32607 MiB，GPU 利用率约 83% | 仍有较大显存余量，但不是空闲状态 |
| Isaac Sim | 未发现运行中的 Isaac Sim 进程 | 可以排除已有 Isaac Sim 重复启动 |
| DORA 采集器 | 仍在运行：`dora-openarm-dataset-recorder`、`dora-openarm-ros2-bridge`、DORA session 进程 | 采集栈没有退出；是否正在写新 episode 还需在采集终端确认 |
| nurec 训练进程 | PID `2790033`，约占用 9750 MiB GPU | 属于 `worker` 用户，不要结束该进程 |
| 真机 bringup | PID `3240388` 和 `3241010`，使用 `can0/can1` | 当前真机 ROS 2 系统仍在运行 |
| rosbag record | 本次检查未发现独立的 `ros2 bag record` 进程 | 不能据此判断 DORA recorder 已停止 |

结论：当前不满足“没有数据采集和 GPU 占用后再启动 Isaac Sim”的条件，因此暂时不要直接启动 Isaac Sim GUI。DORA 采集器属于当前用户，但在确认本轮采集已经结束前不要强制结束；nurec 属于其他用户，更不能结束。若只做不连接 ROS 的 Isaac Sim 单机 GUI 测试，可以保留真机 bringup，但应关闭 ROS bridge 或使用独立的 `ROS_DOMAIN_ID`，并接受与 nurec 共享 GPU 可能导致启动慢或再次闪退的风险。

启动前在真机终端重新执行以下检查，确认 DORA 采集已结束、没有 rosbag 进程后再启动：

~~~bash
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
ps -eo user,pid,ppid,etime,cmd | grep -E 'dora-openarm|dora run|ros2 bag record|isaac-sim|kit/python' | grep -v grep
pgrep -af 'ros2 bag record|dora-openarm-dataset-recorder|dora-openarm-ros2-bridge|isaac-sim|kit/python' || true
~~~

只有在 DORA 采集终端明确退出、上述命令不再显示 recorder/bridge，并确认 GPU 资源可用后，才进入 Isaac Sim 启动步骤。不要用 `kill -9` 清理未知 PID；清理动作需要先核对 PID、用户和采集输出目录。

### A-114：真机断电状态记录

2026-09-11：用户确认机器人当前没有上电，电机指示灯不亮。因此本轮不能执行真机动作、静止基线或 CAN/关节反馈采集。

| 项目 | 当前状态 | 记录 |
|---|---|---|
| 机器人主电源 | 未确认/未上电 | 不发送运动命令 |
| 电机指示灯 | 不亮 | 不能把 ROS bringup 进程当成电机已连接 |
| 真机采集 | 暂停 | 等主电源、急停和驱动器状态确认后再做 |
| Isaac Sim 独立运行 | 可以准备 | 使用无 ROS bridge 模式，避免把空的真机反馈当作数据 |

恢复真机采集前，按以下顺序人工确认并填写，不要反复发送控制命令：

~~~text
电源线/电源开关: ______________________
急停是否释放: [ ] 是  [ ] 否
电源指示灯: ____________________________
各电机指示灯: __________________________
CAN 接口/终端电阻: _____________________
驱动器故障码: __________________________
恢复时间: ______________________________
~~~

确认电机指示灯恢复、驱动器无故障后，再在真机终端检查 `/joint_states` 是否持续发布；在此之前不运行 B、C、F 采集步骤。当前若只测试 Isaac Sim GUI，可暂时不启动真机 bringup，并使用：

~~~bash
cd ~/isaacsim
./isaac-sim.sh --/isaac/startup/ros_bridge_extension= --/rtx/ecoMode/enabled=True
~~~

该 GUI 仍会与 nurec 进程共享 GPU；若再次闪退，应等待 nurec 释放显存后重试。

### A-115：Isaac Sim 闪退诊断

2026-09-11：对当前安装执行了无窗口兼容性检查：

~~~bash
cd ~/isaacsim
./isaac-sim.compatibility_check.sh --no-ros-env --no-window --/app/window/enabled=false
~~~

检查结果为 `System checking result: PASSED`。检测到 RTX 5090、驱动 595.84、Ubuntu 24.04.4、约 101 GB RAM 和约 307 GB 可用磁盘空间；这些项目均通过检查。安装目录约 17 GB，`kit/kit`、`apps/isaacsim.exp.full.kit` 和 RTX 场景库文件均存在。

最近四次完整 GUI 闪退具有相同特征：启动约 10 秒后，在 `librtx.scenedb.plugin.so` 和 `libcarb.scenerenderer-rtx.plugin.so` 的 RTX 场景数据库/渲染线程中崩溃，最后一个命令是 `SetLightingMenuModeCommand`。因此当前结论是“完整 GUI 的 RTX 启动问题或资源/配置冲突”，不是 ROS 包缺失，也不是基本安装文件缺失。

处理顺序：

1. 不要先重装。先等待 nurec 训练进程释放 GPU，或在另一张 GPU/空闲时段测试；当前 nurec 曾占用约 13--14 GB 显存并使 GPU 利用率超过 90%。
2. 用全新用户配置和缓存做一次诊断启动。该操作只重置 Isaac Sim 用户配置并清理缓存，不修改工程文件：

~~~bash
cd ~/isaacsim
./isaac-sim.sh --reset-user --clear-cache --no-ros-env \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
~~~

3. 若仍在同一个 RTX 场景库位置闪退，暂时不要接 ROS bridge，也不要加载机器人场景；先用兼容性检查器和最小 Kit 应用验证基础运行，再考虑升级到受支持的 Isaac Sim 版本。当前目录版本是 `5.1.0-rc.19`，官方文档已将 5.1.0 标为不再维护，后续迁移应优先使用受支持的稳定版本。
4. 每次复现后保存最新日志：

~~~bash
find ~/.nvidia-omniverse/logs/Kit -type f -mmin -30 -print
find ~/.local/share/ov/data/Kit -type f -name 'crash_*.txt' -mmin -30 -print
~~~

当前不应把“兼容性检查通过”理解为“完整 GUI 一定不会崩溃”；它只证明驱动、GPU、操作系统和基础运行环境满足要求。正式 Isaac Sim/ROS 对齐前，必须先完成一次无 ROS bridge 的稳定 GUI 启动。

### A-116：显存与 RTX 崩溃的区分

2026-09-11：再次检查时 GPU 状态为 RTX 5090 已用约 20666/32607 MiB，利用率约 93%；其中 nurec 进程 PID `2790033` 占用约 20080 MiB。当前只剩约 11.9 GB 显存，不适合同时启动完整 Isaac Sim GUI 和 RTX 渲染。

不过最近崩溃日志没有出现 `out of memory` 或显存分配失败字样，调用栈仍固定在 `librtx.scenedb.plugin.so` 和 `libcarb.scenerenderer-rtx.plugin.so`。因此：

```text
显存竞争：当前存在，可能诱发或放大闪退；
单纯显存不足：日志暂未证实；
RTX 场景数据库/版本配置问题：仍需在 GPU 空闲时复现确认。
```

判定步骤：

1. 等 nurec 结束或显存降到低于 4 GB，再测试一次；不要结束其他用户的 PID `2790033`。
2. GPU 空闲时仍用 `--reset-user --clear-cache --no-ros-env` 启动；若仍在相同 RTX 栈崩溃，就不再把显存作为主要根因。
3. 此时优先升级到受支持的稳定 Isaac Sim 版本，而不是反复重装当前 `5.1.0-rc.19`。

### A-117：其他可能原因排查

除显存竞争外，还发现以下可能因素：

| 因素 | 证据 | 判断 |
|---|---|---|
| ROS 环境污染 | 当前 shell 有 `PYTHONPATH=/opt/ros/jazzy/lib/python3.12/site-packages`、ROS Jazzy 的 `LD_LIBRARY_PATH`；Isaac Sim 5.1 自带 Python 3.11 | 高度可疑。`--no-ros-env` 只跳过脚本自动设置，不会清除当前 shell 已有变量 |
| Isaac Sim 版本 | 本地 `VERSION` 为 `5.1.0-rc.19` | 旧的候选版本；完整 GUI 可能存在 RTX 回归问题 |
| RTX 场景数据库 | 四次崩溃均在 `librtx.scenedb.plugin.so` / `libcarb.scenerenderer-rtx.plugin.so` | 与 ROS/缓存/驱动加载冲突都可能相关；日志没有 OOM |
| GPU 资源竞争 | nurec 曾占用 20 GB 以上，GPU 利用率约 93% | 可能诱发，但不能单独解释固定的 RTX 栈崩溃 |
| IOMMU | Kit 启动时有 `IOMMU is enabled` warning | 当前只有 warning，暂不作为首要原因 |
| CPU governor | 启动时为 `powersave` | 只影响性能和启动时间，暂未见导致崩溃的证据 |
| 显示/基础驱动 | 兼容性检查器已通过，Vulkan、显示器和驱动均识别正常 | 基础安装和硬件兼容性基本成立 |

先用干净环境启动，避免 ROS 3.12 库污染 Isaac Sim 3.11 运行时：

~~~bash
cd ~/isaacsim
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
    -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
    -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
    -u RMW_IMPLEMENTATION -u ROS_AUTOMATIC_DISCOVERY_RANGE \
    ./isaac-sim.sh --no-ros-env --reset-user --clear-cache \
      --/isaac/startup/ros_bridge_extension= \
      --/rtx/ecoMode/enabled=True
~~~

该命令只用于无 ROS bridge 的 GUI 诊断。若在 nurec 释放 GPU 后仍然在同一个 RTX 栈崩溃，则优先升级 Isaac Sim 稳定版本；不要继续修改 URDF、ROS 或机器人配置来规避这个启动崩溃。

### A-118：最新日志结论和干净环境启动

2026-09-11：最新粘贴日志中的 `omni.isaac.* has been deprecated` 全部是兼容性 warning，不是闪退原因。文件末尾明确显示 `段错误`，调用栈仍为 `librtx.scenedb.plugin.so` → `libcarb.scenerenderer-rtx.plugin.so`。本次复现使用了 `--reset-user --clear-cache`，仍然得到同一栈，因此单纯用户缓存问题的可能性下降。

当前 shell 还继承了 ROS Jazzy 的 Python 3.12 和 ROS 库路径。为排除库冲突，已新增 `alignment/start_isaacsim_clean.sh`，它会清除 ROS/Python/动态库环境后再启动 Isaac Sim：

~~~bash
cd ~/openarm_ws
bash alignment/start_isaacsim_clean.sh \
  --reset-user \
  --clear-cache \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
~~~

判定规则：

* 干净环境且 GPU 空闲后能稳定打开：根因为 ROS 环境污染或资源竞争，后续连接 ROS 时单独配置 bridge 环境；
* 干净环境且 GPU 空闲后仍在 RTX 场景数据库崩溃：根因更可能是 Isaac Sim `5.1.0-rc.19` 的 RTX/驱动回归，应升级受支持的稳定版本；不要继续修改机器人 URDF 来绕过启动崩溃。

干净环境下的无窗口兼容性检查已实际执行并通过：`System checking result: PASSED`。这进一步说明 ROS 环境隔离和基础安装可用；完整 GUI 的 RTX 段错误仍需在 GPU 资源充足时做最后一次复现。

### A-119：当前显存和环境状态快照

2026-09-11：最新主机检查结果：

```text
GPU：NVIDIA GeForce RTX 5090
显存：21308 / 32607 MiB 已用，约 10770 MiB 可用
GPU 利用率：94%
主要占用：nurec PID 2790033，约 20718 MiB
Isaac Sim：当前未运行
```

当前显存余量不足以保证完整 RTX GUI 稳定启动，暂不启动 Isaac Sim。兼容性检查器在清除 ROS/Python 环境后已通过，因此环境隔离方案可用；交互式 shell 中仍显示 ROS 变量是正常的，必须通过 `start_isaacsim_clean.sh` 启动才会被清除。

### A-120：Isaac Sim 最低空间和显存要求

按官方 Isaac Sim 6.0 x86_64 要求：

| 资源 | 最低 | 推荐/良好 | 说明 |
|---|---:|---:|---|
| 安装磁盘 | 50 GB SSD 可用空间 | 500 GB SSD | 首次下载包与解压目录同时存在时，至少预留约 50 GB；复杂资产和缓存会继续增长 |
| GPU 总显存 | 16 GB | 16 GB 以上；理想 48 GB | 低于 16 GB 的卡运行复杂场景或多传感器容易失败 |
| 系统内存 | 32 GB | 64 GB | Isaac Lab 训练还需要更多内存和显存 |

本机 RTX 5090 有约 32 GB 显存、系统内存约 96 GB、磁盘可用空间约 307 GB，因此硬件总规格满足最低要求。当前 nurec 占用约 20 GB 显存时只剩约 10.7 GB 可用，低于完整 RTX GUI 的安全余量；这属于“运行时可用显存不足”，不是显卡总显存规格不足。

### A-121：主机使用者和占用进程

2026-09-11：主机当前有两个实际用户登录或运行进程：

| 用户 | 来源/会话 | 主要活动 |
|---|---|---|
| `tangyuan` | 本地图形会话；SSH `192.168.18.41`、`192.168.18.37`、`192.168.18.51` | VS Code、README 编辑、DORA 数据采集器/ROS2 bridge；未发现当前运行中的 Isaac Sim |
| `worker` | SSH `192.168.18.61`、`192.168.18.96`、`192.168.18.123`、`192.168.18.165` | nurec 场景重建训练及 TorchInductor 编译子进程 |

GPU 当前主要计算占用是 `worker` 的 nurec PID `2790033`，约占 19--20 GB 显存；不要结束该进程。`tangyuan` 的 DORA recorder、ROS2 bridge 和 UI 进程仍存活，虽然没有单独的 `ros2 bag record` 进程，但它们仍属于数据采集栈。启动 Isaac Sim 前应先确认这些采集进程是否需要保留。

### A-122：停止当前用户采集进程后的显存结果

2026-09-11：按用户授权，仅停止了 `tangyuan` 名下的 DORA quitter、dataset-recorder、ROS2 bridge、command vendor、UI 和对应 DORA session 进程。`worker` 的 nurec、桌面、VS Code 和其他用户进程未停止。

清理后核对：

```text
自己的 DORA/Isaac Sim/真机 bringup 相关进程：已无
worker nurec PID 2790033：仍在运行
GPU：24713 / 32607 MiB 已用
可用显存：约 7365 MiB
GPU 利用率：约 93%
```

DORA 采集器没有占用可观 GPU 显存，因此停止它们没有释放显存；nurec 在清理期间继续增加了显存占用。当前仍不启动完整 Isaac Sim，必须等待 nurec 释放 GPU 后再做干净环境测试。

### A-111：逐步采集操作记录（当前只做第 1 步）

用户尚未采集过硬件信息，因此本轮从“硬件身份确认”开始。第 1 步只读系统和 ROS 信息，不移动机械臂、不发送控制命令、不启动 Isaac Sim。完成并填写下面的结果后，再进入静止基线。

#### 第 1 步：硬件身份和连接状态

打开一个新的终端，不要关闭正在运行的真机 bringup 终端：

~~~bash
cd ~/openarm_ws
source /opt/ros/jazzy/setup.bash
source ~/openarm_ws/install/setup.bash

SESSION_ID="isaacsim_$(date +%Y%m%d_%H%M%S)"
SESSION="alignment/results/isaacsim_migration/${SESSION_ID}"
mkdir -p "$SESSION"/{control,calibration,objects,workspace,vision,bimanual,contact,trajectories,replay}

hostnamectl > "$SESSION/control/host.txt"
uname -a >> "$SESSION/control/host.txt"
ip -details link show can0 can1 > "$SESSION/control/can.txt" 2>&1
lsusb > "$SESSION/control/usb.txt" 2>&1
ros2 node list > "$SESSION/control/ros_nodes.txt"
ros2 topic list > "$SESSION/control/ros_topics.txt"
ros2 topic info /joint_states -v > "$SESSION/control/joint_states_info.txt" 2>&1
ros2 topic echo /joint_states --once > "$SESSION/control/joint_states_once.txt" 2>&1

if command -v rs-enumerate-devices >/dev/null; then
  rs-enumerate-devices > "$SESSION/control/realsense_devices.txt"
fi
if command -v v4l2-ctl >/dev/null; then
  v4l2-ctl --list-devices > "$SESSION/control/v4l2_devices.txt" 2>&1
fi

ros2 pkg prefix openarm_bringup openarm_hardware openarm_teleop_ker \
  > "$SESSION/control/ros_package_prefix.txt" 2>&1
git -C ~/openarm_ws log -1 --oneline > "$SESSION/control/workspace_commit.txt" 2>&1
echo "$SESSION"
~~~

如果 can0 或 can1 不存在，只保留错误文本并在下表写“未发现”，不要执行 CAN 配置、回零或使能命令。相机信息也只读取，不要重新启动相机节点。

填写第 1 步结果：

| 项目 | 结果 |
|---|---|
| session_id/目录 | ________________________________ |
| OpenArm 型号/版本 | ________________________________ |
| 左臂硬件/固件版本 | ________________________________ |
| 右臂硬件/固件版本 | ________________________________ |
| can0 状态/速率 | ________________________________ |
| can1 状态/速率 | ________________________________ |
| /joint_states 发布者 | ________________________________ |
| /joint_states 是否包含左右 7 轴和夹爪 | [ ] 是  [ ] 否 |
| 相机设备/序列号/型号 | ________________________________ |
| 相机 ROS 话题 | ________________________________ |
| 工作区 commit | ________________________________ |
| 未发现项或错误 | ________________________________ |

硬件/固件版本如果不在命令输出中，先不要猜测；从真机 bringup 启动日志、设备标签或厂商工具补录，并把来源写在“未发现项或错误”一栏。第 1 步完成后，再执行 A-110 的 B 步静止 30 秒记录。

### A-112：真机启动脚本和采集执行脚本

#### 1. 启动真机

已有脚本为 alignment/start_real_openarm.sh。它使用双臂 v2.0、can0/can1、真实硬件和 forward_position_controller；启动硬件插件时可能使能电机并执行回零。确认机械臂周围无人、急停可用、CAN 接口接线正确后，在终端 1 执行：

~~~bash
cd ~/openarm_ws
source /opt/ros/jazzy/setup.bash
source ~/openarm_ws/install/setup.bash
bash alignment/start_real_openarm.sh
~~~

看到真机 bringup 正常运行后，保持终端 1 不动。不要同时启动第二个 bringup、旧的 teleop 或第二个 controller_manager。

#### 2. 只读硬件信息采集

在终端 2 执行。该脚本不发送运动命令：

~~~bash
cd ~/openarm_ws
bash alignment/collect_hardware_inventory.sh
~~~

脚本最后打印本轮目录，例如：

~~~text
/home/tangyuan/openarm_ws/alignment/results/isaacsim_migration/isaacsim_YYYYMMDD_HHMMSS
~~~

把这段路径记为 SESSION_DIR，并把硬件/ROS 信息填写回 A-111。

#### 3. 录制静止基线

先确认 SESSION_DIR 下的 control/relevant_topics.txt，再只传入实际存在的话题。最小静止记录命令：

~~~bash
cd ~/openarm_ws
bash alignment/record_topics.sh \
  SESSION_DIR \
  control/idle_30s \
  30 \
  /joint_states /tf /tf_static
~~~

SESSION_DIR 可以写绝对路径，也可以只写 session_id。脚本会先检查话题是否存在，检查失败时不会创建录包，也不会发布任何控制命令。

#### 4. 录制双臂同步短轨迹

确认控制话题名后，将下面的占位话题替换为实际名称：

~~~bash
bash alignment/record_topics.sh \
  SESSION_DIR \
  bimanual/sync_motion_20s \
  20 \
  /joint_states /tf /tf_static \
  <left_action_topic> <right_action_topic> \
  <left_gripper_topic> <right_gripper_topic>
~~~

录包开始后，再用已经批准的安全方式让左右臂同时做 10--20 秒无接触动作；结束后等待脚本返回路径。该脚本只记录话题，不会驱动机械臂。

#### 5. 录制视觉片段

在 control/relevant_topics.txt 中找到实际的 image 和 camera_info 话题，然后执行：

~~~bash
bash alignment/record_topics.sh \
  SESSION_DIR \
  vision/trials_60s \
  60 \
  <image_topic_1> <camera_info_topic_1> \
  <image_topic_2> <camera_info_topic_2>
~~~

每个相机的标定消息另存一份：

~~~bash
ros2 topic echo --once <camera_info_topic> \
  > SESSION_DIR/calibration/camera_info_<camera_id>.yaml
~~~

#### 6. 本轮执行顺序

~~~text
终端 1：bash alignment/start_real_openarm.sh
终端 2：bash alignment/collect_hardware_inventory.sh
终端 2：alignment/record_topics.sh ... control/idle_30s ...
终端 2：alignment/record_topics.sh ... bimanual/sync_motion_20s ...
终端 2：alignment/record_topics.sh ... vision/trials_60s ...
~~~

完成后把 SESSION_DIR、control/relevant_topics.txt 和各录包路径填入 A-110/A-111。先不要修改 offset、URDF、USD 或 Isaac Sim 控制参数；这批数据用于建立迁移前的真机基线。

### A-123：换主机迁移与路径保持方案

2026-09-11：当前任务可以迁移到另一台主机继续。迁移原则是保留 `alignment/results`、`dora`、`ckpts` 和脚本等原始资料；ROS 的 `build/install/log`、Python 虚拟环境和主机驱动在新主机重建。这样不会把旧主机的绝对软链接、ROS 二进制或正在运行的进程带到新主机。

#### 1. 先填写两台主机信息

```text
源主机 IP/用户名: ______________________________
目标主机 IP/用户名: ____________________________
源工作区: /home/tangyuan/openarm_ws
目标工作区: ____________________________________
源 Isaac Sim: /home/tangyuan/isaacsim
目标 Isaac Sim: _________________________________
传输方式: [ ] rsync/SSH  [ ] 移动硬盘  [ ] 其他
```

推荐目标主机也使用 `/home/tangyuan/openarm_ws`。如果用户名或目录不同，所有命令都通过 `NEW_WS` 和 `ISAAC_ROOT` 变量指定，不能直接假定旧的绝对路径仍然存在。

#### 2. 源主机：生成迁移清单

在当前主机执行。该命令只读文件，不停止真机、DORA 或 Isaac Sim：

```bash
cd ~/openarm_ws
bash alignment/export_migration_manifest.sh
```

它会在 `alignment/results/migration_manifest_<时间>/manifest.txt` 保存 Git commit、目录大小、数据文件清单和关键配置的 SHA256。把该清单路径填入本节：

```text
manifest: ______________________________________
源 commit: _____________________________________
清单 SHA256（可选）: ___________________________
```

#### 3. 源主机：传输项目和原始数据

先在目标主机创建目录，再从源主机执行 `rsync`。下面的 `NEW_USER`、`NEW_IP` 和 `NEW_WS` 替换为实际值：

```bash
OLD_WS="$HOME/openarm_ws"
NEW_USER="填写"
NEW_IP="填写"
NEW_WS="/home/填写/openarm_ws"

ssh "$NEW_USER@$NEW_IP" "mkdir -p '$NEW_WS'"

rsync -aH --info=progress2 \
  "$OLD_WS/alignment" \
  "$OLD_WS/src" \
  "$OLD_WS/dora" \
  "$OLD_WS/ckpts" \
  "$NEW_USER@$NEW_IP:$NEW_WS/"
```

如果还需要迁移项目根目录下的映射、YAML、CSV、Parquet 或脚本，再执行：

```bash
rsync -aH --info=progress2 \
  --include='*.yaml' --include='*.yml' --include='*.json' \
  --include='*.csv' --include='*.parquet' --include='*.sh' \
  --exclude='build/' --exclude='install/' --exclude='log/' \
  "$OLD_WS/" "$NEW_USER@$NEW_IP:$NEW_WS/"
```

这两条命令会保留 `alignment/results` 下的历史 CSV、Parquet 和 summary 文件；不要使用 `--delete`，避免删除目标主机上已有资料。

#### 4. 是否复制 Isaac Sim

当前 Isaac Sim 安装在 `~/isaacsim`，约 17 GB。网络足够快时可直接复制；网络慢时在目标主机单独安装同版本更稳：

```bash
# 方案 A：复制现有安装（源主机执行）
rsync -aH --info=progress2 \
  "$HOME/isaacsim/" \
  "$NEW_USER@$NEW_IP:/home/$NEW_USER/isaacsim/"

# 方案 B：不复制，目标主机安装后只记录路径
```

不要复制 `/opt/ros`、NVIDIA 驱动、正在运行的进程、`.ros/log` 或临时缓存。目标主机必须自己安装兼容的 NVIDIA 驱动、ROS 2 Jazzy 和 Isaac Sim 依赖。目标 Isaac Sim 路径记录为：

```text
目标 ISAAC_ROOT: __________________________________
Isaac Sim 版本: ___________________________________
```

#### 5. 目标主机：检查路径并重建 ROS 工作区

在目标主机执行：

```bash
NEW_WS="/home/填写/openarm_ws"
cd "$NEW_WS"
test -f alignment/README.md
test -d alignment/results
test -d src

source /opt/ros/jazzy/setup.bash

# 旧 build/install/log 可能含有源主机绝对软链接，先改名保留，不直接删除
if [[ -d build ]]; then mv build "build.pre_migration_$(date +%Y%m%d_%H%M%S)"; fi
if [[ -d install ]]; then mv install "install.pre_migration_$(date +%Y%m%d_%H%M%S)"; fi
if [[ -d log ]]; then mv log "log.pre_migration_$(date +%Y%m%d_%H%M%S)"; fi

colcon build --symlink-install
source install/setup.bash
```

如果目标工作区仍然是 `/home/tangyuan/openarm_ws`，旧 `build/install` 理论上可以复用，但仍建议按上面步骤重建；若路径、用户名或 ROS 版本改变，必须重建。

#### 6. 目标主机：检查旧绝对路径和 Isaac Sim 启动脚本

```bash
cd "$NEW_WS"
find build install -type l -lname '/home/tangyuan/openarm_ws/*' -print 2>/dev/null || true

ISAAC_ROOT="/home/填写/isaacsim" \
  bash alignment/start_isaacsim_clean.sh --no-window
```

若 `find` 输出旧主机路径，说明仍有旧软链接；不要手工逐个改，重建 `build/install`。先用 `--no-window` 做启动检查，确认不再闪退后再打开 GUI。启动 Isaac Sim 前仍需确认目标主机没有其他用户占用 GPU。

#### 7. 数据和环境的迁移边界

| 内容 | 处理方式 | 备注 |
|---|---|---|
| `alignment/README.md`、脚本、映射 JSON | 复制 | 保留本项目记录和操作路径 |
| `alignment/results/**` | 复制 | 原始 gap、summary、bag 元数据不覆盖 |
| `dora/**`、`ckpts/**` | 复制 | 体积大，传输后用 manifest 核对 |
| `src/**` | 复制并重新 `colcon build` | 保留源码和配置 |
| `build/`、`install/`、`log/` | 不作为最终环境复制 | 旧软链接可能指向源主机 |
| ROS `/opt/ros`、NVIDIA 驱动 | 目标主机重新安装 | 不跨主机复制系统目录 |
| Python/Conda 环境 | 按 requirements/lock 重建 | 不直接复制带二进制扩展的环境 |
| `~/isaacsim` | 可复制或目标机重装 | 版本必须记录一致 |
| 运行中的 DORA/ROS/Isaac 进程 | 不迁移 | 在源主机正常结束后再转移数据 |

#### 8. 目标主机迁移验收

```bash
cd "$NEW_WS"
test -f alignment/README.md
find alignment/results -type f | wc -l
git -C "$NEW_WS" status --short
source /opt/ros/jazzy/setup.bash
source "$NEW_WS/install/setup.bash"
ros2 pkg list | grep -E 'openarm|alignment' || true

# 重新生成目标清单，和源主机 manifest 对照
bash alignment/export_migration_manifest.sh
```

填写验收记录：

| 项目 | 源主机 | 目标主机 | 结果 |
|---|---|---|---|
| 工作区路径 | `________________` | `________________` | `[ ]` |
| `alignment/results` 文件数 | `________________` | `________________` | `[ ]` |
| manifest/关键文件 SHA256 | `________________` | `________________` | `[ ]` |
| Git commit | `________________` | `________________` | `[ ]` |
| ROS 包可见 | `________________` | `________________` | `[ ]` |
| Isaac Sim 版本和启动检查 | `________________` | `________________` | `[ ]` |

迁移完成后，新的采集和 replay 仍统一写入：

```text
<目标工作区>/alignment/results/isaacsim_migration/<session_id>/
```

不要改写旧 session 的路径；新主机只追加新的 `session_id`。完成路径验收后，先做单臂 replay，再做双臂和视觉 replay，最后才继续接触和任务级验证。

### A-124：切换到空闲主机启动 Isaac Sim

2026-09-11：用户在另一台主机检查到 RTX 5090 总显存 32607 MiB，已用 1267 MiB，约 31340 MiB 可用；GPU 利用率 0%，当前没有 Isaac Sim 或训练进程。该主机可直接用于 Isaac Sim GUI，避免与原主机上的 nurec 进程争用显存。

#### 启动前确认安装路径

在新主机执行：

```bash
ISAAC_ROOT="${ISAAC_ROOT:-$HOME/isaacsim}"
if [[ ! -x "$ISAAC_ROOT/isaac-sim.sh" ]]; then
  echo "未找到 $ISAAC_ROOT/isaac-sim.sh，请先设置正确的 ISAAC_ROOT"
  find /home -maxdepth 3 -name isaac-sim.sh -type f 2>/dev/null | head
  exit 1
fi
echo "ISAAC_ROOT=$ISAAC_ROOT"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader
```

#### 直接启动独立 Isaac Sim GUI

独立仿真不连接真机 ROS 时，在新主机执行：

```bash
ISAAC_ROOT="${ISAAC_ROOT:-$HOME/isaacsim}"
cd "$ISAAC_ROOT"
exec env \
  -u PYTHONPATH \
  -u PYTHONHOME \
  -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH \
  -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO \
  -u ROS_VERSION \
  -u ROS_PYTHON_VERSION \
  -u RMW_IMPLEMENTATION \
  "$ISAAC_ROOT/isaac-sim.sh" \
  --no-ros-env \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
```

如果已经把本仓库迁移到新主机，也可以直接使用项目脚本：

```bash
cd ~/openarm_ws
ISAAC_ROOT="$HOME/isaacsim" bash alignment/start_isaacsim_clean.sh \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
```

#### 启动后记录

```text
新主机 IP: ______________________________
新主机用户名: __________________________
Isaac Sim 实际路径: _____________________
启动时间: _______________________________
GUI 是否正常显示: [ ] 是  [ ] 否
启动后显存使用: __________________ MiB
日志路径: _______________________________
```

启动成功后先加载一个简单场景，确认窗口稳定运行 1--2 分钟，再导入 OpenArm 场景。不要在新主机同时启动 DORA 采集器或训练进程；如果需要 ROS 联调，再单独启动 ROS bridge，并记录对应的 `ROS_DOMAIN_ID`。

### A-125：user1 主机上的 Isaac Sim 路径和 Docker 入口

2026-09-11：`user1` 的 `~/isaacsim` 不存在。主机上已发现一份完整安装：`/home/tangyuan/isaacsim/isaac-sim.sh`。该目录属于 `tangyuan`，如果 `user1` 没有目录执行权限，不能直接从该路径启动。当前 Docker 命令还需要先确认 socket 权限，不能把“命令存在”误认为“已经能进入容器”。

#### 1. 先检查 user1 的访问权限

```bash
id
ls -ld /home/tangyuan /home/tangyuan/isaacsim
test -x /home/tangyuan/isaacsim/isaac-sim.sh && echo ISAAC_LAUNCHER_OK || echo ISAAC_PATH_NOT_ACCESSIBLE
```

如果输出 `ISAAC_PATH_NOT_ACCESSIBLE`，不要直接改权限；请管理员选择下面一种方式：

```text
[ ] 把 Isaac Sim 复制/安装到 /home/user1/isaacsim
[ ] 给 user1 授予 /home/tangyuan/isaacsim 的只读和执行权限
[ ] 只使用 Docker，不访问宿主机安装目录
```

#### 2. 检查已有 Docker 容器和镜像

先重新登录一次 `user1`，或执行 `newgrp docker`，再运行：

```bash
docker ps -a --format 'table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}'
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'
docker info
```

如果出现 `permission denied ... /var/run/docker.sock`，记录：

```bash
ls -l /var/run/docker.sock
getent group docker
```

然后由管理员把 `user1` 加入 Docker 用户组并重新登录：

```bash
sudo usermod -aG docker user1
```

不要为了启动 Isaac Sim 修改 Docker socket 为 `666`，也不要删除其他用户的容器。

#### 3. 进入已经存在的 Isaac 容器

从 `docker ps -a` 找到镜像名和容器名后，把占位符替换掉：

```bash
CONTAINER="填写容器名或 ID"
docker start "$CONTAINER"
docker exec -it "$CONTAINER" bash
```

进入容器后检查：

```bash
test -x /isaac-sim/isaac-sim.sh && echo ISAAC_CONTAINER_OK
nvidia-smi
```

如果容器内没有 `/isaac-sim/isaac-sim.sh`，先不要运行 GUI；把 `docker inspect "$CONTAINER"` 中的镜像名、挂载路径和启动命令记录下来，再决定使用哪个入口。

#### 4. 如果只有镜像、没有容器

先在 `docker images` 中找到 Isaac Sim 镜像的完整仓库名和 tag，再使用该镜像创建容器。不要猜测 tag：

```bash
IMAGE="填写 docker images 中的 Isaac Sim 镜像:tag"
docker run --rm -it --gpus all \
  --network host \
  -e DISPLAY="$DISPLAY" \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v "$HOME/openarm_ws":/workspace/openarm_ws \
  "$IMAGE" bash
```

容器内再确认 Isaac Sim 的实际路径；常见路径是 `/isaac-sim`，但以 `find / -maxdepth 3 -name isaac-sim.sh` 的结果为准。若需要持久保存 replay 和采集结果，必须保留 `/workspace/openarm_ws` 挂载。

#### 5. 本机安装的替代方案

如果管理员允许 `user1` 使用宿主机安装，最稳妥是把安装放到 `user1` 自己的 home，再按 A-124 的清洁环境命令启动：

```bash
ISAAC_ROOT="/home/user1/isaacsim"
test -x "$ISAAC_ROOT/isaac-sim.sh"
cd "$ISAAC_ROOT"
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  "$ISAAC_ROOT/isaac-sim.sh" --no-ros-env \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
```

迁移后的工作区路径记录为：

```text
user1 工作区: ____________________________
Isaac Sim 入口: __________________________
Docker 容器/镜像: ________________________
是否挂载 alignment/results: [ ] 是  [ ] 否
```

### A-126：user1 检查结果与最快处理方式

2026-09-11：`user1` 已执行路径、Docker 和 GPU 检查，结果如下：

| 检查项 | 结果 |
|---|---|
| `~/isaacsim/isaac-sim.sh` | 不存在 |
| `/home/tangyuan/isaacsim` | 存在，但 `user1` 无权限访问 |
| `docker ps -a` | 没有显示可用容器 |
| `docker images` | 没有显示 Isaac Sim/NVIDIA 镜像 |
| RTX 5090 | 32607 MiB 总显存，已用约 1267 MiB |

因此当前不能通过 `ISAAC_ROOT` 或 `docker exec` 直接启动。最快方式是由管理员在同一台主机上复制现有安装，不需要重新下载 17 GB 安装包。

#### 方案 A：复制宿主机 Isaac Sim（推荐）

由有 root 权限的账号执行：

```bash
sudo mkdir -p /home/user1/isaacsim
sudo rsync -aH --info=progress2 \
  /home/tangyuan/isaacsim/ /home/user1/isaacsim/
sudo chown -R user1:user1 /home/user1/isaacsim
```

复制完成后，切回 `user1`：

```bash
ISAAC_ROOT=/home/user1/isaacsim
test -x "$ISAAC_ROOT/isaac-sim.sh"
cd "$ISAAC_ROOT"
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  "$ISAAC_ROOT/isaac-sim.sh" --no-ros-env \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
```

#### 方案 B：同时复制 OpenArm 工作区

如果要在 `user1` 继续当前对齐和 replay 任务，再复制项目数据：

```bash
sudo mkdir -p /home/user1/openarm_ws
sudo rsync -aH --info=progress2 \
  --exclude='build/' --exclude='install/' --exclude='log/' \
  /home/tangyuan/openarm_ws/alignment \
  /home/tangyuan/openarm_ws/src \
  /home/tangyuan/openarm_ws/dora \
  /home/tangyuan/openarm_ws/ckpts \
  /home/user1/openarm_ws/
sudo chown -R user1:user1 /home/user1/openarm_ws
```

然后在 `user1` 下重建 ROS 工作区：

```bash
cd /home/user1/openarm_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

#### 方案 C：使用 Docker

当前没有发现本机 Isaac Sim 镜像，所以 Docker 不能立即进入。确认管理员权限后再检查：

```bash
docker ps -a
docker images
docker info
```

只有 `docker images` 显示 Isaac Sim 镜像后，才使用镜像名创建容器；不要使用未知镜像名或删除其他用户容器。容器必须挂载工作区：

```text
/home/user1/openarm_ws  ->  /workspace/openarm_ws
```

当前建议顺序：先执行方案 A，确认 GUI 稳定后，再执行方案 B；暂时不重新下载 Docker 镜像。

### A-127：是否需要迁移当前项目

需要。只要新主机要继续当前 OpenArm 对齐、Isaac Sim replay 或数据分析，就必须迁移项目数据；仅启动一个空白 Isaac Sim GUI 则不需要迁移整个工作区。

#### 必须迁移的内容

```text
alignment/                         # README、采集脚本、gap 和 summary
alignment/results/                 # 原始 CSV、Parquet、rosbag 元数据
src/                               # OpenArm/Isaac 对接源码
dora/                              # 数据采集和转换工程
ckpts/                             # 已有模型/检查点（约 21 GB）
项目根目录下的 YAML/JSON 配置       # 映射、offset、场景参数
```

当前已知规模约为：`alignment` 153 MB、`src` 967 MB、`dora` 955 MB、`ckpts` 约 21 GB。迁移前先生成清单：

```bash
cd ~/openarm_ws
bash alignment/export_migration_manifest.sh
```

#### 不要直接迁移的内容

```text
/opt/ros/jazzy/       # 新主机重新安装 ROS
NVIDIA 驱动和 CUDA     # 新主机按驱动版本安装
build/ install/ log/   # 可能含源主机绝对软链接，目标机重建
正在运行的 ROS/DORA/Isaac 进程
```

#### 源主机执行迁移

把 `NEW_USER`、`NEW_IP` 和 `NEW_WS` 换成实际值：

```bash
OLD_WS="$HOME/openarm_ws"
NEW_USER="user1"
NEW_IP="填写新主机IP"
NEW_WS="/home/user1/openarm_ws"

ssh "$NEW_USER@$NEW_IP" "mkdir -p '$NEW_WS'"
rsync -aH --info=progress2 \
  --exclude='build/' --exclude='install/' --exclude='log/' \
  "$OLD_WS/alignment" "$OLD_WS/src" "$OLD_WS/dora" "$OLD_WS/ckpts" \
  "$NEW_USER@$NEW_IP:$NEW_WS/"
```

如果源主机和目标主机是同一台机器的不同用户，使用管理员账号执行：

```bash
sudo mkdir -p /home/user1/openarm_ws
sudo rsync -aH --info=progress2 \
  --exclude='build/' --exclude='install/' --exclude='log/' \
  /home/tangyuan/openarm_ws/alignment \
  /home/tangyuan/openarm_ws/src \
  /home/tangyuan/openarm_ws/dora \
  /home/tangyuan/openarm_ws/ckpts \
  /home/user1/openarm_ws/
sudo chown -R user1:user1 /home/user1/openarm_ws
```

#### 目标主机重建环境

```bash
cd /home/user1/openarm_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash

test -f alignment/README.md
test -d alignment/results
find build install -type l -lname '/home/tangyuan/openarm_ws/*' -print 2>/dev/null || true
```

如果最后一条命令仍有输出，说明残留了旧主机软链接，应重新移走 `build/` 和 `install/` 后再执行 `colcon build`。

#### Isaac Sim 的处理

Isaac Sim 当前安装约 17 GB。可以复制到新主机的 `/home/user1/isaacsim`，也可以在新主机重新安装同版本；两种方式都要把最终入口记录为：

```text
目标工作区: ______________________________
目标 Isaac Sim: __________________________
Isaac Sim 版本: __________________________
迁移 manifest: ___________________________
```

完成迁移后，所有新采集和 replay 写入：

```text
/home/user1/openarm_ws/alignment/results/isaacsim_migration/<new_session_id>/
```

旧主机的 `alignment/results` 只读保留，不覆盖历史数据。

### A-128：目标主机 192.168.18.72 尚未完成迁移

2026-09-11：在 `user1@192.168.18.72` 执行编译时，出现以下结果：

```text
/home/user1/openarm_ws 不存在
/opt/ros/jazzy/setup.bash 不存在
colcon 未安装
```

这表示目标主机还没有完成文件传输和 ROS 基础环境安装，不能执行 `source install/setup.bash` 或 `colcon build`。源主机的 `export_migration_manifest.sh` 已正常生成清单：

```text
/home/tangyuan/openarm_ws/alignment/results/migration_manifest_20260911_120750/manifest.txt
```

#### 1. 先确认 rsync 是否完成

在源主机执行：

```bash
ssh user1@192.168.18.72 \
  'ls -ld /home/user1/openarm_ws; find /home/user1/openarm_ws/alignment/results -maxdepth 1 -type f | head'
```

如果提示目录不存在，重新传输：

```bash
ssh user1@192.168.18.72 'mkdir -p /home/user1/openarm_ws'

rsync -aH --info=progress2 \
  --exclude='build/' --exclude='install/' --exclude='log/' \
  alignment src dora ckpts \
  user1@192.168.18.72:/home/user1/openarm_ws/
```

传输结束必须看到 rsync 返回 shell 提示符，并再次执行上面的 `ssh ... ls` 验证。

#### 2. 目标主机安装 ROS 和 colcon

在目标主机执行系统检查：

```bash
cat /etc/os-release
uname -m
command -v rsync || true
command -v colcon || true
```

如果目标系统是 Ubuntu 24.04，使用管理员账号安装 ROS 2 Jazzy 和编译工具：

```bash
sudo apt update
sudo apt install -y \
  ros-jazzy-desktop \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-vcstool \
  rsync
```

如果 `sudo` 不可用，把上述命令交给管理员执行；不要在没有 ROS 的情况下继续编译。安装后验证：

```bash
test -f /opt/ros/jazzy/setup.bash
source /opt/ros/jazzy/setup.bash
command -v colcon
ros2 --version
```

#### 3. 目标主机编译迁移后的工作区

```bash
cd /home/user1/openarm_ws
source /opt/ros/jazzy/setup.bash

if [[ -d build ]]; then mv build "build.before_rebuild_$(date +%Y%m%d_%H%M%S)"; fi
if [[ -d install ]]; then mv install "install.before_rebuild_$(date +%Y%m%d_%H%M%S)"; fi
if [[ -d log ]]; then mv log "log.before_rebuild_$(date +%Y%m%d_%H%M%S)"; fi

rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

#### 4. 迁移验收

```bash
cd /home/user1/openarm_ws
test -f alignment/README.md
test -d alignment/results
find alignment/results -type f | wc -l
git status --short 2>/dev/null || true
bash alignment/export_migration_manifest.sh
```

填写结果：

```text
rsync 完成时间: __________________________
目标主机 Ubuntu 版本: ____________________
ROS Jazzy 安装: [ ] 是  [ ] 否
colcon 版本: _____________________________
目标 workspace 文件数: ____________________
目标 manifest 路径: _______________________
```

在 A-128 完成前，不启动 OpenArm ROS bringup，不运行真机采集，也不开始 Isaac Sim replay。先完成文件、ROS 和编译环境三项验收。

### A-129：目标主机文件正在传输

2026-09-11：源主机执行 `rsync` 到 `user1@192.168.18.72:/home/user1/openarm_ws/`，终端显示：

```text
1,404,379,568   6%   110.51MB/s   0:03:05   xfr#110
```

说明 `alignment`、`src`、`dora`、`ckpts` 正在正常传输。必须等待进度达到 100% 且 rsync 返回 shell 提示符后，才能开始目标主机验收。传输期间不要按 `Ctrl+C`，不要启动编译或 Isaac Sim。

传输完成后执行：

```bash
ssh user1@192.168.18.72 \
  'find /home/user1/openarm_ws/alignment/results -type f | wc -l; \
   du -sh /home/user1/openarm_ws/alignment /home/user1/openarm_ws/src \
          /home/user1/openarm_ws/dora /home/user1/openarm_ws/ckpts'
```

Node.js 的 `use --delete-prefix v22.23.2 --silent` 提示只是版本管理器提示，与 rsync、ROS 和 Isaac Sim 迁移无关。

### A-130：工作区迁移完成验收

2026-09-11：目标主机 `user1@192.168.18.72` 已完成工作区数据接收并通过 SSH 远程核对。第一次密码输入失败，第二次连接成功，不影响已完成的 rsync。

```text
目标 alignment/results 文件数: 91
目标 alignment: 155M
目标 src:       967M
目标 dora:      955M
目标 ckpts:      21G
```

这些目录已经在新主机：

```text
/home/user1/openarm_ws/alignment
/home/user1/openarm_ws/src
/home/user1/openarm_ws/dora
/home/user1/openarm_ws/ckpts
```

本次 rsync 没有包含 `/home/tangyuan/isaacsim`，所以 Isaac Sim 仍需单独复制或在目标主机安装。目标主机还没有 ROS Jazzy 和 `colcon`，下一步先安装它们，再重建工作区：

```bash
cd /home/user1/openarm_ws
source /opt/ros/jazzy/setup.bash
rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

在 ROS/colcon 安装并编译成功前，不启动真机 bringup，也不运行 Isaac Sim replay。

### A-131：目标主机缺少 ROS 2 Jazzy 基础环境

2026-09-11：在 `user1@192.168.18.72` 执行工作区编译时确认：

```text
/opt/ros/jazzy/setup.bash 不存在
rosdep 未安装
colcon 未安装
```

因此目标主机当前只有已迁移的项目文件，尚未具备 ROS 编译环境。`source install/setup.bash` 报错是因为工作区还没有成功构建，不是数据丢失。

#### 1. 先确认目标系统版本

在目标主机执行：

```bash
cat /etc/os-release
uname -m
```

只有 Ubuntu 24.04 amd64 才直接按下面的 Jazzy 安装命令执行；如果系统版本不同，先记录版本，不要混装 ROS 二进制包。

#### 2. 由管理员安装 ROS Jazzy 和工具

目标主机需要管理员执行：

```bash
sudo apt update
sudo apt install -y \
  ros-jazzy-desktop \
  python3-colcon-common-extensions \
  python3-rosdep2 \
  python3-vcstool \
  rsync
```

如果提示找不到 `ros-jazzy-desktop`，说明 ROS 2 软件源还没配置；管理员应先按 Ubuntu 24.04 的 ROS 2 Jazzy 安装步骤配置软件源，再重新执行上述命令。不要只安装名为 `colcon` 的独立包来替代 ROS 环境。

安装后由 `user1` 验证：

```bash
test -f /opt/ros/jazzy/setup.bash
source /opt/ros/jazzy/setup.bash
command -v ros2
command -v rosdep
command -v colcon
```

#### 3. 安装依赖并编译迁移工作区

```bash
cd /home/user1/openarm_ws
source /opt/ros/jazzy/setup.bash
rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

完成后记录：

```text
目标 Ubuntu 版本: ______________________
ROS Jazzy 安装完成: [ ] 是  [ ] 否
rosdep 路径: ____________________________
colcon 路径: ____________________________
colcon 编译结果: [ ] 成功  [ ] 失败
失败日志: ______________________________
```

在 A-131 完成前不要启动真机、DORA 采集或 Isaac Sim ROS bridge；Isaac Sim 独立 GUI 可以单独测试，但项目 replay 需要等工作区编译成功。

### A-132：user1 是否可以自行安装

可以自行安装的前提是 `user1` 有 `sudo` 权限，并且目标系统是 Ubuntu 24.04。先在目标主机执行：

```bash
id
groups
sudo -v
```

判断方法：

```text
sudo -v 成功       -> 可以自己安装
sudo: permission denied / 不在 sudoers -> 需要管理员
sudo 命令不存在    -> 需要管理员安装 sudo
```

如果 `sudo -v` 成功，执行 A-131 的安装命令即可：

```bash
sudo apt update
sudo apt install -y \
  ros-jazzy-desktop \
  python3-colcon-common-extensions \
  python3-rosdep2 \
  python3-vcstool \
  rsync
```

如果没有 sudo，单独安装 Python 版 `colcon` 也不能解决问题，因为 `/opt/ros/jazzy/setup.bash` 和 ROS 运行库仍然缺失。此时有三条路：

```text
1. 请管理员安装 ROS Jazzy（推荐）
2. 让管理员把 user1 加入 sudo，并重新登录
3. 使用已准备好的 Isaac Sim/ROS Docker 镜像（当前尚未发现本地镜像）
```

不要尝试把 `/opt/ros` 从另一台主机直接复制过来；ROS 二进制、系统库和驱动必须在目标主机按系统版本安装。

### A-133：切换 tangyuan 本地账号是否需要重新搬运

不一定需要。先区分主机：

| 情况 | 是否重新传输 | 处理方式 |
|---|---|---|
| `tangyuan` 和 `user1` 在同一台物理主机 | 不需要 | 直接使用已有目录，或调整目录权限 |
| 192.168.18.72 是另一台主机，且没有 `/home/tangyuan/openarm_ws` | 需要一次 | 把工作区传到该主机的 tangyuan home |
| 两个账号共享同一个挂载盘 | 不需要 | 使用同一个工作区路径，避免复制两份 21 GB ckpts |

#### 1. 先在目标主机检查 tangyuan 路径

```bash
ls -ld /home/tangyuan /home/tangyuan/openarm_ws /home/tangyuan/isaacsim 2>/dev/null || true
```

如果目录已经存在，不要重新 rsync；直接记录实际路径并使用它：

```text
tangyuan 工作区: __________________________
tangyuan Isaac Sim: ________________________
```

#### 2. 如果目标主机没有 tangyuan 数据

从已有数据的源主机执行一次传输：

```bash
ssh tangyuan@192.168.18.72 'mkdir -p /home/tangyuan/openarm_ws'

rsync -aH --info=progress2 \
  --exclude='build/' --exclude='install/' --exclude='log/' \
  alignment src dora ckpts \
  tangyuan@192.168.18.72:/home/tangyuan/openarm_ws/
```

Isaac Sim 安装单独传输：

```bash
rsync -aH --info=progress2 \
  /home/tangyuan/isaacsim/ \
  tangyuan@192.168.18.72:/home/tangyuan/isaacsim/
```

#### 3. 同一台机器上避免重复复制

如果数据现在属于 `user1`，而 `tangyuan` 也需要使用，优先让管理员设置共享组或 ACL；不要复制 `ckpts` 第二份：

```bash
sudo usermod -aG user1 tangyuan
```

重新登录后验证：

```bash
id tangyuan
test -r /home/user1/openarm_ws/alignment/README.md
test -r /home/user1/openarm_ws/alignment/results/migration_manifest_20260911_120750/manifest.txt
```

如果权限策略不允许共享，则由管理员把目录移动/复制到 `/home/tangyuan/openarm_ws`，并设置归属：

```bash
sudo rsync -aH /home/user1/openarm_ws/ /home/tangyuan/openarm_ws/
sudo chown -R tangyuan:tangyuan /home/tangyuan/openarm_ws
```

切换账号本身不会改变数据；只有目标主机没有对应目录时才需要重新传输。迁移后仍以 `alignment/results` 的原始文件和 manifest 作为唯一验收依据。

### A-134：tangyuan 已登录目标主机

2026-09-11：已成功登录 `tangyuan@192.168.18.72`。下一步只做环境检查，不启动真机、不发送运动命令。

在目标主机执行：

```bash
echo "user=$(whoami) host=$(hostname) home=$HOME"
ls -ld "$HOME/openarm_ws" "$HOME/isaacsim" 2>/dev/null || true
test -f "$HOME/openarm_ws/alignment/README.md" && echo WORKSPACE_OK || echo WORKSPACE_MISSING
test -x "$HOME/isaacsim/isaac-sim.sh" && echo ISAAC_LOCAL_OK || echo ISAAC_LOCAL_MISSING
test -f /opt/ros/jazzy/setup.bash && echo ROS_JAZZY_OK || echo ROS_JAZZY_MISSING
command -v colcon || true
command -v ros2 || true
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader
```

根据结果选择：

```text
WORKSPACE_OK + ROS_JAZZY_OK -> source ROS 后重建/验证工作区
ISAAC_LOCAL_OK              -> 使用 A-124 的清洁启动命令
ISAAC_LOCAL_MISSING         -> 查找 /home/user1/isaacsim 或复制安装
ROS_JAZZY_MISSING           -> 先安装 ROS，不能直接 colcon build
```

如果 `tangyuan` 有管理员权限，可先验证：

```bash
sudo -v
```

只有该命令成功后，才可以自行安装 ROS 2 Jazzy；失败时把安装命令交给管理员。检查结果填写：

```text
目标主机 hostname: ______________________
tangyuan 工作区路径: ____________________
Isaac Sim 路径: _________________________
ROS Jazzy: [ ] 已有  [ ] 缺少
colcon: [ ] 已有  [ ] 缺少
当前 GPU 显存: __________________ MiB
```

### A-135：目标主机 tangyuan 环境仍为空

2026-09-11：在 `tangyuan@192.168.18.72` 检查到：

```text
HOME=/home/tangyuan
WORKSPACE_MISSING
ISAAC_LOCAL_MISSING
ROS_JAZZY_MISSING
RTX 5090: 1134 MiB / 32607 MiB，GPU 利用率 0%
```

说明 GPU 没有问题，但 `tangyuan` 的 home 尚未放置项目和 Isaac Sim。之前传输成功的工作区位于同一目标主机的 `/home/user1/openarm_ws`，不是 `/home/tangyuan/openarm_ws`。

#### 1. 先尝试复用 user1 的已迁移目录

```bash
ls -ld /home/user1 /home/user1/openarm_ws /home/user1/isaacsim 2>/dev/null || true
test -r /home/user1/openarm_ws/alignment/README.md && echo USER1_WORKSPACE_READABLE || true
test -x /home/user1/isaacsim/isaac-sim.sh && echo USER1_ISAAC_READABLE || true
```

如果能读，优先直接使用 `/home/user1/openarm_ws`，不复制 21 GB 的 `ckpts`。如果不能读，由管理员设置共享权限，或执行下面的复制方案。

#### 2. 将已迁移目录复制到 tangyuan（同一台目标主机）

由管理员执行：

```bash
sudo rsync -aH --info=progress2 \
  /home/user1/openarm_ws/ \
  /home/tangyuan/openarm_ws/
sudo chown -R tangyuan:tangyuan /home/tangyuan/openarm_ws
```

如果 `/home/user1/isaacsim` 也已存在：

```bash
sudo rsync -aH --info=progress2 \
  /home/user1/isaacsim/ \
  /home/tangyuan/isaacsim/
sudo chown -R tangyuan:tangyuan /home/tangyuan/isaacsim
```

#### 3. 如果 user1 目录也不存在

从原始源主机重新传输到目标主机的 tangyuan 账号：

```bash
rsync -aH --info=progress2 \
  --exclude='build/' --exclude='install/' --exclude='log/' \
  alignment src dora ckpts \
  tangyuan@192.168.18.72:/home/tangyuan/openarm_ws/
```

Isaac Sim 安装单独传输：

```bash
rsync -aH --info=progress2 \
  /home/tangyuan/isaacsim/ \
  tangyuan@192.168.18.72:/home/tangyuan/isaacsim/
```

当前目标主机只显示空闲 GPU，不能据此判断 Isaac Sim 已安装；必须先完成路径和文件验收，再安装 ROS Jazzy、编译工作区，最后启动 Isaac Sim。

### A-136：确认 user1 目录是否存在及是否可访问

2026-09-11：`tangyuan@192.168.18.72` 执行针对 `/home/user1/openarm_ws` 和 `/home/user1/isaacsim` 的检查没有任何输出。下一步只检查目录和账号信息：

```bash
whoami
ls -la /home
getent passwd user1 || true
ls -ld /home/user1 2>&1 || true
namei -l /home/user1/openarm_ws 2>&1 || true
namei -l /home/user1/isaacsim 2>&1 || true
```

判断：

```text
/home/user1 不存在       -> user1 迁移发生在另一台主机，需重新传输到本机
/home/user1 存在但拒绝访问 -> 需要管理员授予目录执行/读取权限
/home/user1/openarm_ws 存在 -> 可以共享该工作区，不必重新复制
/home/user1/isaacsim 不存在 -> Isaac Sim 仍需复制或重新安装
```

如果确认本机没有这些目录，应从原始源主机执行：

```bash
rsync -aH --info=progress2 \
  --exclude='build/' --exclude='install/' --exclude='log/' \
  alignment src dora ckpts \
  tangyuan@192.168.18.72:/home/tangyuan/openarm_ws/
```

当前不要用 `find /` 代替权限检查，也不要直接修改 `/home` 的权限；先根据 `ls -la /home` 和 `namei -l` 的结果选择路径。

### A-137：tangyuan 账号确认需要共享或重新迁移

2026-09-11：目标主机检查结果：

```text
/home/user1 存在，但 tangyuan 无权访问
/home/user1/openarm_ws -> Permission denied
/home/user1/isaacsim  -> Permission denied
/home/tangyuan/openarm_ws -> 不存在
/home/tangyuan/isaacsim  -> 不存在
```

如果继续使用 `tangyuan` 账号，有两种做法。

#### 方案 A：管理员在本机复制已有 user1 工作区（避免跨主机重传）

先确认 user1 目录确实包含迁移数据，再由管理员执行：

```bash
sudo ls -ld /home/user1/openarm_ws
sudo test -f /home/user1/openarm_ws/alignment/README.md

sudo rsync -aH --info=progress2 \
  --exclude='build/' --exclude='install/' --exclude='log/' \
  /home/user1/openarm_ws/ \
  /home/tangyuan/openarm_ws/
sudo chown -R tangyuan:tangyuan /home/tangyuan/openarm_ws
```

如果 user1 目录中已有 Isaac Sim，再执行：

```bash
sudo rsync -aH --info=progress2 \
  /home/user1/isaacsim/ \
  /home/tangyuan/isaacsim/
sudo chown -R tangyuan:tangyuan /home/tangyuan/isaacsim
```

#### 方案 B：从原始源主机重新传到 tangyuan

只有在本机 `/home/user1` 没有完整数据时才使用。以下命令必须在保存原始数据的源主机执行：

```bash
rsync -aH --info=progress2 \
  --exclude='build/' --exclude='install/' --exclude='log/' \
  alignment src dora ckpts \
  tangyuan@192.168.18.72:/home/tangyuan/openarm_ws/

rsync -aH --info=progress2 \
  /home/tangyuan/isaacsim/ \
  tangyuan@192.168.18.72:/home/tangyuan/isaacsim/
```

#### 迁移后验证

```bash
ls -ld /home/tangyuan/openarm_ws /home/tangyuan/isaacsim
test -f /home/tangyuan/openarm_ws/alignment/README.md
test -x /home/tangyuan/isaacsim/isaac-sim.sh
```

验证通过后，再在 `tangyuan` 账号下安装 ROS Jazzy、`rosdep`、`colcon` 并重建工作区。不要同时保留两份 `ckpts`，除非磁盘空间足够。

### A-138：从源主机迁移到 tangyuan 后清理 user1 数据

2026-09-11：用户决定以 `tangyuan` 账号作为目标主机的唯一工作账号。执行顺序固定为：

```text
源主机传输 -> 目标 tangyuan 验收 -> 再删除 /home/user1 下的副本
```

不得在验收前删除 user1 数据。

#### 1. 在源主机执行传输

下面命令必须在保存原始项目和 Isaac Sim 的源主机执行。把 `SOURCE_WS`、`SOURCE_ISAAC` 改为源主机实际路径，把 `TARGET_IP` 改为 `192.168.18.72`：

```bash
SOURCE_WS="$HOME/openarm_ws"
SOURCE_ISAAC="$HOME/isaacsim"
TARGET_USER="tangyuan"
TARGET_IP="192.168.18.72"

ssh "$TARGET_USER@$TARGET_IP" \
  'mkdir -p /home/tangyuan/openarm_ws /home/tangyuan/isaacsim'

rsync -aH --info=progress2 --checksum \
  --exclude='build/' --exclude='install/' --exclude='log/' \
  "$SOURCE_WS/" \
  "$TARGET_USER@$TARGET_IP:/home/tangyuan/openarm_ws/"

rsync -aH --info=progress2 --checksum \
  "$SOURCE_ISAAC/" \
  "$TARGET_USER@$TARGET_IP:/home/tangyuan/isaacsim/"
```

Isaac Sim 约 17 GB，工作区和 `ckpts` 约 23 GB，传输期间保持终端连接，不要中断。

#### 2. 在目标主机验收 tangyuan 副本

传输结束后登录目标主机执行：

```bash
test -f /home/tangyuan/openarm_ws/alignment/README.md
test -x /home/tangyuan/isaacsim/isaac-sim.sh
du -sh /home/tangyuan/openarm_ws/alignment \
       /home/tangyuan/openarm_ws/src \
       /home/tangyuan/openarm_ws/dora \
       /home/tangyuan/openarm_ws/ckpts \
       /home/tangyuan/isaacsim

cd /home/tangyuan/openarm_ws
bash alignment/export_migration_manifest.sh
```

只有以下条件全部满足，才允许删除 user1 副本：

```text
[ ] README.md 可读
[ ] alignment/results 文件数量与源主机一致
[ ] Isaac Sim 启动文件可执行
[ ] 目标 manifest 已生成
[ ] 关键文件 SHA256 与源主机一致
```

#### 3. 删除 user1 副本

确认验收完成后，在目标主机执行以下精确删除命令：

```bash
sudo rm -rf -- /home/user1/openarm_ws /home/user1/isaacsim
```

该命令不会删除 `user1` 账号，只删除两个明确目录。删除后确认空间释放：

```bash
test ! -e /home/user1/openarm_ws
test ! -e /home/user1/isaacsim
df -h /home
```

如果没有 sudo，不要尝试绕过权限；让管理员执行删除。删除完成后，后续统一使用：

```text
/home/tangyuan/openarm_ws
/home/tangyuan/isaacsim
```

### A-139：删除 user1 副本前的最终确认

2026-09-11：目标主机 `tangyuan` 已生成迁移清单：

```text
/home/tangyuan/openarm_ws/alignment/results/migration_manifest_20260911_135231/manifest.txt
```

`test` 命令成功时不会打印文字，因此删除前使用下面的失败保护检查：

```bash
set -e
test -f /home/tangyuan/openarm_ws/alignment/README.md
test -x /home/tangyuan/isaacsim/isaac-sim.sh
test -s /home/tangyuan/openarm_ws/alignment/results/migration_manifest_20260911_135231/manifest.txt
echo 'TARGET_COPY_VALID'
```

只有看到 `TARGET_COPY_VALID` 后，才执行精确删除：

```bash
sudo rm -rf -- \
  /home/user1/openarm_ws \
  /home/user1/isaacsim
```

删除后确认：

```bash
test ! -e /home/user1/openarm_ws && echo USER1_WORKSPACE_REMOVED
test ! -e /home/user1/isaacsim && echo USER1_ISAAC_REMOVED
df -h /home
```

这不会删除 `user1` Linux 账号，只删除其工作区和 Isaac Sim 副本。删除后唯一工作路径为 `/home/tangyuan/openarm_ws` 和 `/home/tangyuan/isaacsim`。

### A-140：磁盘空间与 GPU 显存是两个独立资源

2026-09-11：删除 user1 副本后确认：

```text
/dev/nvme0n1p4  1.7T  1.6T  28G  99%  /
```

这表示根分区只剩约 28 GB 磁盘空间；此前 `nvidia-smi` 显示的 1134 MiB / 32607 MiB 是 GPU 显存，两者互不等价。GPU 空闲不代表磁盘空闲。

#### 1. 先定位一级目录占用

在目标主机执行，只读检查：

```bash
sudo du -xhd1 / 2>/dev/null | sort -h
sudo du -xhd1 /home 2>/dev/null | sort -h
sudo du -xhd1 /var 2>/dev/null | sort -h
sudo du -xhd1 /opt 2>/dev/null | sort -h
```

再找最大的文件：

```bash
sudo find / -xdev -type f -printf '%s\t%p\n' 2>/dev/null \
  | sort -n | tail -40 \
  | numfmt --field=1 --to=iec
```

如果 Docker 正在使用磁盘，再检查：

```bash
docker system df 2>&1
sudo du -sh /var/lib/docker 2>/dev/null || true
```

#### 2. 当前项目已知占用

源工作区中已知较大的目录包括 `ckpts` 约 21 GB、Isaac Sim 约 17 GB；它们不能在未确认备份前删除。优先把一级目录和最大文件列表保存到：

```bash
mkdir -p /home/tangyuan/openarm_ws/alignment/results/host_inventory
sudo du -xhd1 / 2>/dev/null | sort -h \
  > /home/tangyuan/openarm_ws/alignment/results/host_inventory/disk_du_root.txt
sudo du -xhd1 /home 2>/dev/null | sort -h \
  > /home/tangyuan/openarm_ws/alignment/results/host_inventory/disk_du_home.txt
```

#### 3. 清理原则

```text
可以优先检查：用户缓存、旧日志、确认无用的 Docker dangling 镜像
不要直接删除：ckpts、Isaac Sim、alignment/results、其他用户目录、/opt/ros
不要执行：rm -rf /、docker system prune -a（未确认前）
```

本轮目标是先找到占用来源，再决定是否清理。至少保留 50 GB 可用磁盘空间后，再进行 Isaac Sim 安装、缓存或大规模 replay。

### A-141：清理 user1 挂载副本并启动 Isaac Sim的安全顺序

2026-09-11：用户要求删除 `user1` 中本项目挂载/复制的资源，然后启动 Isaac Sim。由于 `tangyuan` 账号此前检查不到自己的 Isaac Sim，删除前必须先确认目标副本已经存在；不删除整个 `/home/user1`，只处理明确的项目目录。

#### 1. 删除前检查（目标主机执行）

```bash
if test -x /home/tangyuan/isaacsim/isaac-sim.sh \
   && test -f /home/tangyuan/openarm_ws/alignment/README.md; then
  echo "tangyuan_copy_ready=0"
else
  echo "tangyuan_copy_ready=1"
fi

sudo du -sh /home/user1/openarm_ws /home/user1/isaacsim 2>/dev/null || true
```

如果输出 `tangyuan_copy_ready=1`，先不要删除 user1；应先把源主机的工作区和 Isaac Sim 复制到 `/home/tangyuan`。

#### 2. 删除明确的 user1 副本

只有看到 `tangyuan_copy_ready=0` 后执行：

```bash
sudo rm -rf -- \
  /home/user1/openarm_ws \
  /home/user1/isaacsim

test ! -e /home/user1/openarm_ws
test ! -e /home/user1/isaacsim
```

该命令不删除 `user1` 账号、其他目录或 Docker 数据卷。

#### 3. 启动 tangyuan 的 Isaac Sim

```bash
ISAAC_ROOT=/home/tangyuan/isaacsim
test -x "$ISAAC_ROOT/isaac-sim.sh"
cd "$ISAAC_ROOT"
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  "$ISAAC_ROOT/isaac-sim.sh" --no-ros-env \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
```

启动前确认磁盘至少有 50 GB 可用；当前只有约 28 GB，若启动时需要创建缓存，可能因磁盘不足失败。必要时先清理已确认无用的缓存或日志，再启动。

### A-142：tangyuan 清洁启动命令

```bash
ISAAC_ROOT=/home/tangyuan/isaacsim
cd "$ISAAC_ROOT"

env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  "$ISAAC_ROOT/isaac-sim.sh" \
  --no-ros-env \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
```

该命令只启动独立 Isaac Sim，不连接真机 ROS。启动前必须满足：

```text
/home/tangyuan/isaacsim/isaac-sim.sh 存在且可执行
/home/tangyuan/openarm_ws/alignment/README.md 存在
GPU 显存和磁盘空间可用
```

### A-143：Isaac Sim 5.1 在 RTX SceneDB 阶段崩溃的诊断

2026-09-11：最新日志显示：

```text
Isaac Sim: 5.1.0-rc.19
GPU: NVIDIA GeForce RTX 5090
Driver: 595.58.03
Graphics API: Vulkan
VRAM: 1134 MiB / 32607 MiB
RAM: 约 33.6 GB 可用
Fatal backtrace: librtx.scenedb.plugin.so -> libcarb.scenerenderer-rtx.plugin.so
```

结论：这是 Isaac Sim 5.1.0 与 NVIDIA 595.x（R590）驱动在 RTX SceneDB/渲染器初始化阶段的兼容性崩溃，不是显存不足。`omni.isaac.* has been deprecated` 只是兼容性提示；`Cannot setup ExternalDragDrop without a default window` 和 `crashreport.gui exited with code 127` 出现在崩溃之后，不是首要原因。

NVIDIA 开发者答复指出，Isaac Sim 5.1.0 验证的 Linux 驱动是 580.65.06，595.x 分支会触发同类 `librtx.scenedb.plugin.so` 崩溃；该现象已在多种 RTX 40/50 系列显卡上复现：

- [NVIDIA Developer Forum：Isaac Sim 5.1.0 与 595.x 驱动的 SceneDB 崩溃](https://forums.developer.nvidia.com/t/isaac-sim-5-1-0-crashes-on-startup-with-rtx-4090-on-ubuntu-24-04-4-segfaulting-in-librtx-scenedb-plugin-so-after-iommu-was-disabled/371957)
- [Isaac Sim 6.0 官方系统要求（Linux 驱动 580.95.05）](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/installation/requirements.html)

#### 推荐修复顺序

1. **优先方案：**使用与目标 Isaac Sim 版本匹配的 580 分支驱动。Isaac Sim 5.1 使用已验证的 580.65.06；如果迁移到 Isaac Sim 6.0，按官方要求使用 580.95.05。驱动切换需要管理员权限并重启系统。
2. **版本方案：**保留当前 595 驱动时，不继续使用 Isaac Sim 5.1.0-rc.19；改用已针对 RTX 50 系列和当前驱动验证过的 Isaac Sim 版本，并重新运行兼容性检查。
3. **不建议的临时方案：**仅添加 `--/rtx/verifyDriverVersion/enabled=false` 只能跳过版本检查，不能修复 SceneDB 崩溃；本日志对应的同类案例已验证该参数无效。

#### 驱动切换前记录

```bash
nvidia-smi --query-gpu=name,driver_version,memory.used,memory.total \
  --format=csv,noheader
cat /etc/os-release
uname -r
```

驱动由管理员切换后，再确认：

```bash
nvidia-smi
cd /home/tangyuan/isaacsim
./isaac-sim.compatibility_check.sh --no-ros-env --no-window \
  --/app/window/enabled=false --/app/quitAfter=10
```

兼容性检查通过后再启动 GUI。不要为了处理这些 warning 去修改项目代码或批量替换 `omni.isaac.*` 导入；当前崩溃发生在应用代码加载之前的 RTX 插件初始化阶段。

### A-144：无管理员权限时的替代方案与是否需要重新下载

2026-09-11：当前日志表明 Isaac Sim 5.1.0-rc.19 已加载扩展，随后在 `librtx.scenedb.plugin.so` 的 RTX 初始化阶段段错误。显存约 31 GB 可用，RAM 约 33 GB 可用，因此重新下载同一份 Isaac Sim 5.1 并不能解决当前驱动兼容问题。

当前主机关键环境：

```text
Ubuntu 24.04.4
RTX 5090
NVIDIA Driver 595.58.03
Isaac Sim 5.1.0-rc.19
```

NVIDIA 已确认 595.x 驱动与 Isaac Sim 5.1.0 的 RTX SceneDB 存在已知崩溃；Isaac Sim 5.1 推荐 580.65.06。Isaac Sim 6.0 官方测试驱动为 Linux 580.95.05，升级版本也不能保证在 595.x 上稳定。[NVIDIA 已知问题说明](https://forums.developer.nvidia.com/t/isaac-sim-5-1-0-crashes-on-startup-with-rtx-4090-on-ubuntu-24-04-4-segfaulting-in-librtx-scenedb-plugin-so-after-iommu-was-disabled/371957) [Isaac Sim 6.0 系统要求](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/installation/requirements.html)

#### 先确认两台主机的差异

在当前主机和上一台主机分别执行并保存输出：

```bash
nvidia-smi --query-gpu=name,driver_version,memory.used,memory.total \
  --format=csv,noheader
grep -R -m1 -E "appVersion|lib_isaacSim_buildVersion|gpuDriver_0|gpu_0|Graphics API" \
  ~/.local/share/ov/data/Kit/Isaac-Sim\ Full/5.1 2>/dev/null || true
```

如果上一台主机的 Isaac Sim 版本、驱动分支或渲染后端不同，不能把“上一台能运行”归因于同一环境。若上一台也只是兼容性检查通过、GUI 没有持续运行，则两台主机实际表现是一致的。

#### 无管理员权限时的可行路径

```text
路径 1（最快）：在上一台能运行 Isaac Sim 的主机执行仿真/replay，本机只通过 rsync 传输结果
路径 2：使用管理员已准备好的 Isaac Sim Docker 镜像；当前主机没有发现本地 Isaac 镜像
路径 3：请求管理员把驱动切换到 580 分支，再继续使用现有 Isaac Sim 5.1
路径 4：升级 Isaac Sim 6.0，并按官方要求使用匹配的 580 驱动
```

没有管理员权限时，不能自行替换内核 NVIDIA 驱动；Conda、Python 虚拟环境或重新解压 Isaac Sim 不会改变驱动分支。仅使用 `--/rtx/verifyDriverVersion/enabled=false` 也不能修复已经发生的 SceneDB 段错误。

#### 复用上一台主机进行 replay

如果上一台主机确实能稳定打开 GUI，建议把它作为 Isaac Sim 执行主机：

```bash
# 在上一台主机运行，路径按实际安装填写
cd /home/tangyuan/isaacsim
./isaac-sim.sh --no-ros-env --/rtx/ecoMode/enabled=True

# 在当前主机保存/同步项目结果
rsync -aH --info=progress2 \
  /home/tangyuan/openarm_ws/alignment/results/ \
  tangyuan@当前主机IP:/home/tangyuan/openarm_ws/alignment/results/
```

当前根分区只有约 28 GB 可用空间，而 Isaac Sim 6.0 官方最低建议 50 GB SSD；因此在未清理磁盘前，不要重新下载大型 Isaac Sim 安装包或容器镜像。

### A-145：复用上一台主机的 Docker Isaac 环境

2026-09-11：用户确认上一台主机曾配置过 Docker。Docker 镜像存储在各主机本地；当前目标主机没有显示 Isaac Sim 镜像，并不代表源主机的镜像已丢失。

#### 1. 在上一台源主机检查 Docker

```bash
docker ps -a --format 'table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}'
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}' \
  | grep -Ei 'isaac|nvidia|openarm' || true
docker system df
```

如果能找到以前的 Isaac 容器，优先直接在源主机运行它，不迁移镜像：

```bash
CONTAINER="填写已有容器名或ID"
docker start "$CONTAINER"
docker exec -it "$CONTAINER" bash
```

#### 2. 目标主机复用镜像（不重新下载）

如果源主机只有镜像、没有可用容器，先记录完整镜像名：

```bash
IMAGE="填写 docker images 输出的完整镜像:tag"
```

镜像较大时不要先生成临时 tar 文件，直接从源主机流式传到目标主机：

```bash
# 在目标主机执行，SOURCE_IP 改为上一台主机 IP
SOURCE_IP="填写源主机IP"
ssh "$SOURCE_IP" "docker save '$IMAGE'" | docker load
```

如果目标主机 Docker 没有权限，先由管理员修复 `/var/run/docker.sock` 权限；`newgrp docker` 只刷新组身份，不能创建不存在的镜像。

导入后验证：

```bash
docker images | grep -Ei 'isaac|nvidia|openarm'
docker run --rm --gpus all "$IMAGE" nvidia-smi
```

#### 3. 容器环境的兼容性边界

Docker 会携带 Isaac Sim 的用户态库，但仍使用宿主机 NVIDIA 内核驱动。因此当前宿主机的 595.84 驱动仍可能影响 Isaac Sim 5.1 的 RTX 初始化；只有源主机容器在同一驱动上实际稳定运行，才能把它作为可行方案。不要仅凭镜像导入成功就判定渲染问题已解决。

填写记录：

```text
源主机 IP: ______________________________
源 Docker 镜像: _________________________
源容器名/ID: ____________________________
目标导入结果: [ ] 成功  [ ] 失败
容器内 Isaac Sim 版本: __________________
容器内 GPU 测试: [ ] 通过  [ ] 失败
```

### A-146：上一台与新主机的环境对比及新主机启动条件

2026-09-11：上一台主机的实际输出为：

```text
GPU: RTX 5090
Driver: 595.84
Isaac Sim: 5.1.0
现有多份 Isaac-Sim Full/5.1 crash_*.txt 与 .dmp.toml
```

新主机的实际输出为：

```text
GPU: RTX 5090
Driver: 595.58.03
Isaac Sim: 5.1.0-rc.19 / 5.1.0
RTX SceneDB 初始化时段错误
```

两台主机都使用 595.x 驱动和 Isaac Sim 5.1，因此旧主机并非已证明能稳定运行 GUI；现有 crash 文件说明它也发生过同类失败。兼容性检查通过只说明硬件规格被识别，不能证明 RTX 渲染器能正常启动。

#### 新主机开启 Isaac Sim 的必要条件

| 条件 | 当前状态 | 处理 |
|---|---|---|
| `/home/tangyuan/isaacsim/isaac-sim.sh` | 已迁移后应存在 | 用 `test -x` 验证 |
| `/home/tangyuan/openarm_ws` | 已迁移后应存在 | 用 `test -f alignment/README.md` 验证 |
| 可用磁盘 | 约 28 GB，低于 50 GB 建议 | 先清理或扩容 |
| 驱动与 Isaac Sim 5.1 兼容 | 不满足，595.x | 使用 580.65.06，需管理员和重启 |
| 直接启动 GUI | 不可靠 | 驱动修正后再执行 |

驱动修正后，在新主机使用：

```bash
ISAAC_ROOT=/home/tangyuan/isaacsim
cd "$ISAAC_ROOT"
./isaac-sim.compatibility_check.sh --no-ros-env --no-window \
  --/app/window/enabled=false --/app/quitAfter=10

env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  "$ISAAC_ROOT/isaac-sim.sh" --no-ros-env \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
```

如果无法切换驱动，当前新主机没有可靠的本地 GUI 启动路径。重装相同的 Isaac Sim 5.1、清理 Python 环境或使用同一版本的 Docker 都不会改变宿主机 595.x 驱动；Docker 只能作为“源容器已在同一类驱动上实际稳定运行”时的复用方案。

### A-147：Isaac Sim 5.1 启动失败的最终日志证据

2026-09-11：本次粘贴的启动日志来自 `Isaac Sim 5.1.0`，运行在 RTX 5090、NVIDIA 驱动 `595.84`、Ubuntu 24.04.4 上。程序完成了大部分扩展加载，随后在 RTX 场景渲染器初始化期间发生段错误。

| 证据 | 日志值 | 结论 |
|---|---:|---|
| 崩溃模块 | `librtx.scenedb.plugin.so`，经 `libcarb.scenerenderer-rtx.plugin.so`、`libomni.hydra.rtx.plugin.so` | 是 RTX 渲染器/驱动兼容问题，不是 OpenArm、ROS 或某个 Isaac 扩展配置错误。 |
| 空闲显存 | `31432 MiB / 32607 MiB` | 显存充足，排除显存不足。 |
| 空闲主存 | `71995 MiB / 96301 MiB` | 主存充足，排除内存不足。 |
| GPU | RTX 5090，`sm_120` | GPU 被 Warp 正确识别；不是 CUDA 设备缺失。 |
| 驱动 | `595.84` | 与新主机的 `595.58.03` 同属 R595 分支；两台主机都不应继续把该组合视为稳定环境。 |

日志里的 `omni.isaac.* deprecated` 和 `pxr.Semantics deprecated` 都是弃用告警，不会引起本次段错误。`crashreport` 的后续消息也只是崩溃后的报告过程，不是首因。

**处理结论：**不要继续反复启动、不要重新下载相同的 Isaac Sim 5.1，也不要通过清显存解决。要在本机稳定使用 GUI，需要将 NVIDIA 驱动改为官方验证过的 R580 分支并重启；若无法变更驱动，改用一台已验证稳定的远程 Isaac 主机执行仿真。Docker 仍使用宿主机 NVIDIA 内核驱动，不能保证绕过 R595 问题。

#### A-147.1：是否可自行修复驱动

在目标主机以 `tangyuan` 登录后先执行：

```bash
sudo -v
```

- 命令成功且未显示“not in the sudoers file”或认证失败：当前账号可自行安装驱动；驱动切换会中断图形会话并需要重启。
- 命令失败：普通用户不能修改 NVIDIA 内核模块；不重新下载 Isaac Sim，也不继续重复启动，改用可用远程主机或等待具备权限的人处理。

可用 `nvidia-smi --query-gpu=driver_version --format=csv,noheader` 在重启后确认驱动版本。目标是 R580 分支，而不是当前 R595。

### A-148：目标主机自行切换至 R580 驱动

适用条件：以目标主机的 `tangyuan` 账号登录，`sudo -v` 成功。该操作会替换当前 R595 NVIDIA 驱动、影响图形桌面，并且必须重启。执行前保存其他工作；若通过 SSH 远程操作，确认有重启后重新登录该主机的方式。

不要手工执行 `apt remove nvidia-*`，也不要使用 NVIDIA `.run` 安装包。让 APT 处理同一驱动系列的替换关系。

#### 1. 查看 R580 是否由当前软件源提供

```bash
sudo -v
sudo apt update
apt-cache policy nvidia-driver-580
```

输出出现 `Candidate:` 且不是 `(none)` 时继续。安装会下载驱动包，但不会下载或覆盖 OpenArm 工作区和 Isaac Sim 目录。

#### 2. 安装并重启

```bash
sudo apt install -y nvidia-driver-580
sudo reboot
```

重启会断开终端和关闭图形桌面。系统回来后重新登录，确认安装结果：

```bash
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
```

验收条件：RTX 5090 正常显示，驱动版本以 `580.` 开头。若版本仍是 `595.`，不要启动 Isaac Sim；保留 `apt` 输出以便诊断。

#### 3. 清洁环境启动 Isaac Sim

```bash
cd /home/tangyuan/openarm_ws
ISAAC_ROOT=/home/tangyuan/isaacsim

bash alignment/start_isaacsim_clean.sh \
  --/isaac/startup/ros_bridge_extension= \
  --/rtx/ecoMode/enabled=True
```

首次只验证空场景窗口能稳定停留，不加载 OpenArm、ROS bridge、DORA 或重放轨迹。窗口稳定后再进入 URDF/USD 导入和轨迹 replay。

#### A-148.1：驱动切换的影响范围

R580 驱动安装不会修改 `/home/tangyuan/openarm_ws`、Isaac Sim 安装目录、ROS bag、DORA 数据或其他项目文件；APT 只会替换系统级 NVIDIA 驱动包。

但它**会影响整台主机**：安装后重启会中断所有登录会话、图形桌面、显示输出、GPU 训练、CUDA 程序、Docker GPU 容器和其他用户正在运行的显卡任务。驱动切换完成并验证前，这些程序不能依赖 GPU。只有在 `nvidia-smi` 中没有需要保留的 GPU 进程、且确认这台共享主机允许重启时，才能执行 A-148 的安装命令。

### A-149：迁移目标改为 Isaac Sim 6.0.1

2026-09-11：目标版本改为 Isaac Sim `6.0.1`，原因是当前 Isaac Sim `5.1.0-rc.19` 在 RTX 5090 上于 `librtx.scenedb.plugin.so` 崩溃。Isaac Sim 6.0.1 是 NVIDIA 2026-06 发布的 Linux x86_64 workstation 版本；官方工作站安装方式是将 `isaac-sim-standalone-6.0.1-linux-x86_64.zip` 解压到独立目录，再执行 `post_install.sh`。不要覆盖现有 `~/isaacsim` 的 5.1 安装。

#### 当前检查结果

| 项目 | 结果 |
|---|---|
| 现有 Isaac | 仅发现 `~/isaacsim`，版本 `5.1.0-rc.19+release.26219.9c81211b` |
| 6.0.1 安装/压缩包 | 未在 `/home/tangyuan` 找到 |
| 根分区空间 | 约 255 GB 可用，满足 6.0.1 workstation 安装的 50 GB 最低建议 |
| GPU 内核模块 | `580.173.02` 已加载 |
| NVIDIA 用户态工具 | 同时残留 580 与 595 软件包，`nvidia-smi` 当前无法与驱动通信 |

**先决条件：**在下载或启动 6.0.1 前，`nvidia-smi` 必须恢复正常，并能显示 RTX 5090、580.x 驱动和显存信息。当前不能通过安装新的 Isaac 版本绕过一个已经不可用的 NVIDIA 驱动。

#### 6.0.1 的用户目录安装方案（驱动恢复后执行）

下载官方 Linux x86_64 的 6.0.1 压缩包到 `~/Downloads`，然后使用独立目录：

```bash
set -euo pipefail
IS6="$HOME/isaacsim-6.0.1"
ARCHIVE="$HOME/Downloads/isaac-sim-standalone-6.0.1-linux-x86_64.zip"

test -f "$ARCHIVE"
mkdir -p "$IS6"
unzip "$ARCHIVE" -d "$IS6"
cd "$IS6"
./post_install.sh
```

首次验证不加载 ROS、OpenArm、DORA 或任何已有场景：

```bash
IS6="$HOME/isaacsim-6.0.1"
cd "$IS6"
./isaac-sim.compatibility_check.sh --no-window --/app/quitAfter=10

env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  "$IS6/isaac-sim.sh" --no-ros-env --reset-user \
  --/isaac/startup/ros_bridge_extension=
```

6.0.1 首次启动会编译/预热 shader，GUI 空窗口可能停留数分钟；只有终端没有段错误且窗口稳定后，才进入 OpenArm URDF/USD 导入和 replay。

#### A-149.1：为什么现有版本打不开

当前“打不开”的版本是 **Isaac Sim 5.1.0-rc.19**；Isaac Sim 6.0.1 尚未安装，因此没有 6.0.1 的启动结果。

5.1 的直接故障证据是日志中的 `SIGSEGV`：`librtx.scenedb.plugin.so` → `libcarb.scenerenderer-rtx.plugin.so` → `libomni.hydra.rtx.plugin.so`。这是 Isaac 的 RTX 场景渲染器在 RTX 5090 与当时 R595 (`595.84`) 驱动组合下初始化时崩溃。崩溃时有 31.4 GiB 空闲显存和约 72 GiB 空闲主存，所以不是资源不足；弃用告警、ROS 环境和 OpenArm 模型都不在该崩溃调用链中。

此外，目前主机 `nvidia-smi` 无法与驱动通信，说明系统 GPU 驱动栈现在也不健康。即便换成 6.0.1，若 `nvidia-smi` 仍失败，Isaac 无法使用 RTX 渲染。先恢复 `nvidia-smi`，再把 6.0.1 作为独立版本测试，才能区分“5.1 特定兼容问题”和“主机驱动问题”。

### A-150：新空闲主机上的 Isaac Sim 6.0.1 启动修复流程

目标：不再运行 5.1，在新空闲主机以用户目录安装并验证 6.0.1。`~/isaacsim-6.0.1` 与旧的 `~/isaacsim` 相互独立，不会覆盖 OpenArm 工作区、ROS 配置或系统驱动。

#### 1. 先做只读预检

```bash
hostname
nvidia-smi --query-gpu=name,driver_version,memory.used,memory.total --format=csv,noheader
df -h "$HOME"
find "$HOME" -maxdepth 4 -name isaac-sim.sh -printf '%p\n' 2>/dev/null
```

继续条件：`nvidia-smi` 能正常显示 GPU 和显存；主目录所在分区至少有 50 GB 可用空间。若 `nvidia-smi` 报“couldn't communicate with the NVIDIA driver”，停止在此处：这是主机驱动问题，安装 Isaac 6.0.1 不会修复它。

#### 2. 安装到独立用户目录

在 NVIDIA 官方 6.0.1 下载页取得 Linux x86_64 压缩包，保存为：
`~/Downloads/isaac-sim-standalone-6.0.1-linux-x86_64.zip`。

```bash
set -euo pipefail
IS6="$HOME/isaacsim-6.0.1"
ARCHIVE="$HOME/Downloads/isaac-sim-standalone-6.0.1-linux-x86_64.zip"

test -f "$ARCHIVE"
mkdir -p "$IS6"
unzip "$ARCHIVE" -d "$IS6"
cd "$IS6"
./post_install.sh
```

#### 3. 先运行 Compatibility Checker

不要 source ROS、Conda 或 OpenArm 环境：

```bash
IS6="$HOME/isaacsim-6.0.1"
cd "$IS6"
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  ./isaac-sim.compatibility_check.sh --no-window --/app/quitAfter=10
```

仅当它成功退出，才运行 GUI。

#### 4. 清洁启动 6.0.1 空场景

```bash
IS6="$HOME/isaacsim-6.0.1"
cd "$IS6"
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  ./isaac-sim.sh --no-ros-env --reset-user \
  --/isaac/startup/ros_bridge_extension=
```

此步只验证空窗口稳定，不导入 OpenArm、不启动 ROS bridge、不加载 DORA 或 replay。首次 shader 预热可持续数分钟。若仍出现 `librtx.scenedb.plugin.so` 段错误，保存 crash 文件和终端最后 80 行；这才需要检查该主机驱动与 6.0.1 的兼容性，不能再归因于 OpenArm。

#### A-150.1：6.0.1 ZIP 的可恢复下载与局域网复用

不使用 Docker 镜像，也不需要先下载 5 个完整本地资产包。OpenArm 的首个空场景、URDF/USD 导入与 replay 验证只需要 Isaac Sim 核心 ZIP；需要 NVIDIA 示例场景或完全离线资产时才追加资产包。

官方核心 ZIP：

```text
https://downloads.isaacsim.nvidia.com/isaac-sim-standalone-6.0.1-linux-x86_64.zip
```

官方 MD5：`65e2c2e83e2461ce0f33b0732d0ee4a3`。

优先使用 `aria2c` 的断点续传和多连接下载；该命令只写入当前用户的 `~/Downloads`，不修改系统：

```bash
mkdir -p "$HOME/Downloads"
cd "$HOME/Downloads"

aria2c -c -x 8 -s 8 -k 1M --file-allocation=none \
  --checksum=md5=65e2c2e83e2461ce0f33b0732d0ee4a3 \
  -o isaac-sim-standalone-6.0.1-linux-x86_64.zip \
  'https://downloads.isaacsim.nvidia.com/isaac-sim-standalone-6.0.1-linux-x86_64.zip'
```

若没有 `aria2c`，用已安装的 `curl` 单连接续传：

```bash
cd "$HOME/Downloads"
curl -fL -C - --retry 10 --retry-all-errors --retry-delay 5 \
  -o isaac-sim-standalone-6.0.1-linux-x86_64.zip \
  'https://downloads.isaacsim.nvidia.com/isaac-sim-standalone-6.0.1-linux-x86_64.zip'
md5sum isaac-sim-standalone-6.0.1-linux-x86_64.zip
```

校验输出必须为：

```text
65e2c2e83e2461ce0f33b0732d0ee4a3  isaac-sim-standalone-6.0.1-linux-x86_64.zip
```

若实验室内另一台机器已有同一版本的**官方 ZIP**，优先走局域网复制，能中断续传且不依赖外部镜像：

```bash
mkdir -p "$HOME/Downloads"
rsync -aH --partial --append-verify --info=progress2 \
  <user>@<lan_host>:/absolute/path/isaac-sim-standalone-6.0.1-linux-x86_64.zip \
  "$HOME/Downloads/"
md5sum "$HOME/Downloads/isaac-sim-standalone-6.0.1-linux-x86_64.zip"
```

只有 MD5 一致后执行 A-150 的解压步骤；不要使用来源和校验值不明的第三方 ZIP 镜像。

#### A-150.2：下载完成后的空间回收规则

6.0.1 下载慢时，不要中断后从头下载；`aria2c -c` 与 `curl -C -` 都会续传。

删除规则按顺序执行：

1. **先保留** `isaac-sim-standalone-6.0.1-linux-x86_64.zip`，直到 MD5 校验正确、6.0.1 解压完成、Compatibility Checker 通过且空场景稳定启动；
2. 上述条件通过后，ZIP 只是可重新下载的安装介质，可以删除以释放空间：`rm "$HOME/Downloads/isaac-sim-standalone-6.0.1-linux-x86_64.zip"`；
3. 旧的 `~/isaacsim`（5.1）只能在 6.0.1 已成功启动后考虑删除；删除前先运行 `du -sh "$HOME/isaacsim" "$HOME/isaacsim-6.0.1"` 确认路径；
4. **绝不删除** `~/openarm_ws`、`alignment/results/`、DORA 记录、轨迹、ROS bag 或不确定来源的“搬运文件”。它们不是 Isaac 安装副本，而是项目和验证数据。

用户所说“之前搬过来的两个文件”在执行删除前必须对应到两个绝对路径和 `du -sh` 输出；未明确路径时不运行 `rm`。

### A-151：Isaac Sim 6.0.1 Compatibility Checker 通过

2026-09-11：新空闲主机的 6.0.1 Compatibility Checker 返回 `System checking result: PASSED`。

| 项目 | 检查结果 |
|---|---|
| GPU | RTX 5090，supported |
| 驱动 | `595.58.03`，checker 标为 supported |
| 显存 | 34.19 GB，good |
| CPU/RAM | i7-14700KF、67.19 GB RAM，supported/good |
| 磁盘 | 322.28 GB 可用，enough |
| 无图形显示 | SSH 会话未设置 `DISPLAY`，不是 GPU 或 Isaac 故障 |
| Compatibility Checker | `PASSED` |

`failed to open the default display`、`zenity Failed to open display` 和 GLFW 的告警来自 SSH headless 会话。不要在该 SSH 会话直接运行 GUI 版 `isaac-sim.sh` 并期待本地窗口；先做 headless 烟雾测试：

```bash
IS6="$HOME/isaacsim-6.0.1"
cd "$IS6"
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  ./isaac-sim.sh --no-ros-env --no-window \
  --/app/quitAfter=20 \
  --/app/file/ignoreUnsavedOnExit=1
```

成功条件：20 秒后正常退出，没有 `Fatal`、`Segmentation fault` 或 `librtx.scenedb`。

需要从 SSH 远程查看场景时，使用发行包自带的 headless WebRTC 服务，而不是 X11 转发或虚拟显示：

```bash
IS6="$HOME/isaacsim-6.0.1"
cd "$IS6"
./isaac-sim.streaming.sh
```

然后在本地工作站使用 Isaac Sim WebRTC Streaming Client 连接。服务会持续占用终端，使用 `Ctrl+C` 正常停止。只有先完成无窗口烟雾测试后才启动流服务；再之后才连接 ROS bridge、导入 OpenArm 和执行 replay。

#### A-151.1：Fabric 接口版本告警的处理

无窗口烟雾测试中出现：

```text
Warning: Possible version incompatibility. Attempting to load omni::fabric::IStageReaderWriter with version v0.16 against v0.14/v0.15.
```

这表示某个扩展请求的 Fabric 接口版本与已加载接口不同；单独出现时只是兼容性告警，不能据此判定启动失败。当前不清除缓存、不重装扩展、不修改系统。

本轮判断标准是进程在 `--/app/quitAfter=20` 后是否以退出码 `0` 正常结束，且日志中没有 `Fatal`、`Segmentation fault`、`core dumped` 或 `librtx.scenedb`。测试终端返回提示符后立刻执行 `echo $?`：

- `0`：该告警可接受，进入 WebRTC 流服务；
- 非 `0` 或出现 Fatal：保存终端最后 80 行和 `~/.nvidia-omniverse/logs/Kit/` 中本次日志，再诊断，不把它当作普通告警忽略。

#### A-151.2：6.0.1 无窗口烟雾测试通过

2026-09-11：用户确认 A-151 的无窗口测试可以启动，故新空闲主机上的 Isaac Sim 6.0.1 核心运行环境可用。此前 Fabric `IStageReaderWriter` 版本告警未阻止启动，不作为当前阻塞项。

下一步需要远程查看场景时，以相同用户在服务器终端运行：

```bash
IS6="$HOME/isaacsim-6.0.1"
cd "$IS6"
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  ./isaac-sim.streaming.sh
```

该命令启动 headless Isaac Sim WebRTC 服务并持续占用终端；不要关闭终端。随后从本地有显示器的工作站使用 Isaac Sim WebRTC Streaming Client 连接。服务端停止使用 `Ctrl+C`。在 WebRTC 空场景成功显示前，不启动 ROS bridge、不导入 OpenArm、不执行轨迹 replay。

#### A-151.3：为什么 SSH 下没有 Isaac 界面，以及如何查看

`isaac-sim.streaming.sh` 的设计就是 headless：日志显示 `Isaac Sim Full Streaming Version: 6.0.1`、`omni.kit.livestream.webrtc` 和 `isaacsim.exp.full.streaming` 已加载，说明服务端已启动；它不会在 SSH 终端或 SSH 客户端上弹出 GUI。

1. **保持服务器终端运行**，等待输出出现：

   ```text
   Isaac Sim Full Streaming App is loaded.
   ```

2. 在服务器另开一个 SSH 终端，只读确认 IP 和端口：

   ```bash
   hostname -I
   ss -lnt | grep 49100 || true
   ss -lun | grep 47998 || true
   ```

   同一局域网使用 `hostname -I` 的内网 IP。默认 WebRTC 信令端口是 TCP `49100`，媒体流端口是 UDP `47998`。

3. 在**自己有图形桌面的本地工作站**下载并安装 Isaac Sim WebRTC Streaming Client 2.0.0（不要安装在运行服务的 SSH 终端），启动客户端，将默认 `127.0.0.1` 改成服务器的内网 IP，然后点 `Connect`。

不要用 SSH X11 转发、VNC 或 NoMachine 直接承载远程 Isaac GUI；对于远程/headless 主机，官方推荐 WebRTC。流服务仅适合可信局域网，端口不带认证或加密，不要暴露到公网。若客户端黑屏，先确认服务端已输出 loaded，再确认服务器防火墙允许 TCP 49100 和 UDP 47998；不要在未确认主机策略前自行修改防火墙。

#### A-151.4：安装 WebRTC 客户端并连接服务端

客户端安装在**本地有桌面的工作站**，不是运行 `isaac-sim.streaming.sh` 的 SSH 服务端。官方 Linux x86_64 客户端为 `isaacsim-webrtc-streaming-client-2.0.0-linux-x86_64.deb`，MD5 为 `07bd252432fb92b93bdb33b337455827`。

在本地桌面终端执行：

```bash
cd "$HOME/Downloads"

curl -fL -C - --retry 10 --retry-all-errors --retry-delay 5 \
  -o isaacsim-webrtc-streaming-client-2.0.0-linux-x86_64.deb \
  'https://downloads.isaacsim.nvidia.com/isaacsim-webrtc-streaming-client-2.0.0-linux-x86_64.deb'

md5sum isaacsim-webrtc-streaming-client-2.0.0-linux-x86_64.deb
sudo apt install ./isaacsim-webrtc-streaming-client-2.0.0-linux-x86_64.deb
```

校验值必须是：

```text
07bd252432fb92b93bdb33b337455827  isaacsim-webrtc-streaming-client-2.0.0-linux-x86_64.deb
```

服务端另开终端取得同一局域网可达 IP：

```bash
ip -4 -o addr show scope global | awk '{print $4}'
```

在本地桌面运行：

```bash
isaacsim-webrtc-streaming-client
```

在客户端连接界面中，将默认服务器 `127.0.0.1` 改成服务端的 IPv4 地址（去掉 `/24` 子网后缀），保持默认端口，点击 `Connect`。同一时刻只允许一个客户端连接。连接前确认服务端终端已输出 `Isaac Sim Full Streaming App is loaded.`。

#### A-151.5：WebRTC 客户端已安装

2026-09-11：`isaacsim-webrtc-streaming-client-2.0.0-linux-x86_64.deb` 的 MD5 为 `07bd252432fb92b93bdb33b337455827`，与官方值一致；`isaacsim-webrtc-streaming-client (2.0.0-429)` 已成功安装，并注册命令 `/usr/bin/isaacsim-webrtc-streaming-client`。

APT 的 `_apt` 无法访问 `~/Downloads` 而临时以 root 读取本地 `.deb` 的提示不影响安装。不要执行提示中的 `sudo apt autoremove`，其中列出的 NVIDIA firmware 可能属于主机级驱动依赖，与本轮客户端安装无关。

下一步：服务器流服务保持运行且已显示 `Isaac Sim Full Streaming App is loaded.` 时，在本地桌面终端执行：

```bash
isaacsim-webrtc-streaming-client
```

将客户端的服务器字段从 `127.0.0.1` 改为服务端内网 IPv4 地址，再点击 `Connect`。若客户端无法启动，保存错误文本；不要自行修改 `sysctl`、防火墙或 NVIDIA 驱动。

### A-152：WebRTC 黑屏排查与双主机职责

#### WebRTC 黑屏

服务端 `hostname -I` 返回的地址中，使用与本地客户端同一实验室网段的：`192.168.18.72`。不要填 `172.17.0.1`、`10.42.22.0`、`10.42.22.1` 或 `240.72.0.1`，这些是 Docker/VPN/虚拟网络接口。

客户端使用 `192.168.18.72` 后仍黑屏时，在**服务端**另开 SSH 终端执行以下只读检查：

```bash
ss -lnt | grep ':49100' || true
ss -lun | grep ':47998' || true
find ~/.nvidia-omniverse/logs/Kit -type f -mmin -10 -print | tail -10
```

同时在正在运行 `isaac-sim.streaming.sh` 的终端确认是否已出现：

```text
Isaac Sim Full Streaming App is loaded.
```

只有出现 loaded 且 TCP 49100、UDP 47998 正在监听，客户端才应连接。若仍黑屏，保存服务端终端最后 80 行及上述三条命令输出；不要关闭防火墙、修改 `sysctl` 或重装 Isaac。

#### 机器人和摇操臂不迁线

真机 CAN/USB 驱动、机器人电源控制和摇操臂都继续连接到**旧主机**。不需要、也不应为了 Isaac Sim 把它们拔到新主机：

| 主机 | 职责 | 是否直接发送真机命令 |
|---|---|---|
| 旧主机 | CAN/USB 驱动、真机 bringup、摇操臂、真机记录 | 是，唯一真机控制者 |
| 新主机 `192.168.18.72` | Isaac Sim 6.0.1、USD/URDF、离线 replay、WebRTC 显示 | 否，当前阶段禁止直连真机控制器 |
| 本地桌面 | WebRTC 客户端显示 | 否 |

第一阶段保持新主机不启用 ROS bridge，以离线轨迹 replay 验证 Isaac。之后若需要真实 ROS 数据联调，让旧主机只发布硬件状态/记录数据，新主机使用明确的 `sim` 命名空间订阅或回放；不要把 Isaac Sim 的控制 topic 直接路由给真机，也不要让两台主机同时拥有同一组真机控制器。

#### A-152.1：服务账号与日志目录必须一致

`user1` 的 home 下没有 `~/.nvidia-omniverse/logs/Kit`，而之前 6.0.1 的日志路径是 `/home/tangyuan/.nvidia-omniverse/...`。这说明当前用 `user1` 检查端口，但流服务可能由 `tangyuan` 启动。日志与服务进程都归启动 Isaac 的账号所有。

先在任意账号下确认所有者：

```bash
ps -eo user,pid,etime,cmd | grep -E '[i]saac-sim.streaming|[k]it/kit|[i]saac-sim.sh'
```

若输出的用户是 `tangyuan`，使用该账号检查最新日志（只读）：

```bash
sudo -u tangyuan bash -lc '
LOG=$(find "$HOME/.nvidia-omniverse/logs/Kit" -type f -name "kit_*.log" \
  -printf "%T@ %p\\n" | sort -nr | head -1 | cut -d" " -f2-)
echo "$LOG"
tail -n 100 "$LOG"
'
```

不要把不同用户的 `HOME`、Isaac 配置目录或缓存混用。服务端、日志检查和 Isaac 安装最好都使用同一个账号；WebRTC 客户端可以在另一台本地桌面机器、另一个账号下运行。

#### A-152.2：黑屏期间服务端实际状态与重启方式

2026-09-11：服务端日志持续产生 `/Render/...ViewportTexture_0` 的渲染帧，已到 frame `33679`；没有 Fatal 或段错误。最后的 `^C` 表明服务由用户正常停止，并非 Isaac 崩溃。因此当前服务已经停止，客户端不会再显示画面。

重新以**启动服务的 tangyuan 账号**运行以下命令，并保持该终端不关闭。显式填写实验室内网 IP，避免 WebRTC 将 Docker/VPN 虚拟网卡地址作为媒体候选地址：

```bash
IS6="$HOME/isaacsim-6.0.1"
cd "$IS6"
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  ./isaac-sim.streaming.sh \
  --/exts/omni.kit.livestream.app/primaryStream/publicIp=192.168.18.72 \
  --/exts/omni.kit.livestream.app/primaryStream/signalPort=49100 \
  --/exts/omni.kit.livestream.app/primaryStream/streamPort=47998
```

服务启动完成后，在客户端填：服务器 `192.168.18.72`、Signal `49100`、Stream `47998`。连接测试期间不要在服务端按 `Ctrl+C`；只有结束本轮远程查看时才使用 `Ctrl+C`。`ss -lun` 未立即列出 UDP 47998 不足以判定失败，WebRTC 的媒体 socket 可能在协商后才显示；服务端持续渲染帧才是已加载的直接证据。

#### A-152.3：WebRTC 服务端重复启动排查

2026-09-11：两份终端输出逐行相同，均包含 `Isaac Sim Full Streaming Version: 6.0.1-rc.7`、`omni.kit.livestream.webrtc` 和 `isaacsim.exp.full.streaming`。这说明两个终端运行的是同一条 `isaac-sim.streaming.sh` 服务端命令；它们都不是 WebRTC Client。

只保留一个服务端实例。第二个实例会竞争 GPU，以及 TCP `49100` 和 UDP `47998`，导致客户端黑屏、连接失败或不稳定。服务端启动日志中的以下内容均为可接受的启动信息：

```text
Could not import system rclpy: No module named 'rclpy'
Attempting to load internal rclpy for ROS Distro: jazzy
rclpy loaded
Active user not found. Using default user [kiosk]
Unable to detect Omniverse Cache Server
```

本轮不连接真机 ROS，因此 ROS 2 bridge 的内部 rclpy 回退无需处理；`kiosk` 和 Cache 警告也不会阻止 WebRTC 画面。

正确分工：

```text
终端 1（新主机 SSH）：只运行一个 isaac-sim.streaming.sh，保持运行。
终端 2（新主机 SSH）：只用于 ss/日志/显存检查，不启动第二个 Isaac Sim。
图形桌面：运行 Isaac Sim WebRTC Streaming Client，连接 192.168.18.72:49100/47998。
```

如果已经启动两份服务端，立即在其中一个终端按一次 `Ctrl+C`，保留另一份继续启动；不要在保留的服务端终端按 `Ctrl+C`。待保留实例至少出现持续的 `Simulating ... sensor(s)` 或 frame 日志后，再在 WebRTC Client 点击 Connect。

#### A-152.4：信令端口可达但 WebRTC 客户端无画面

2026-09-11：从客户端主机执行 `nc -vz -w 3 192.168.18.72 49100` 已成功，说明服务端 TCP 信令端口可达。该检查不验证实际视频；WebRTC 图像仍依赖 UDP `47998` 的媒体协商。

按以下顺序排查，且始终保留唯一一个服务端实例：

1. 服务端终端持续运行 `isaac-sim.streaming.sh`，不要按 `Ctrl+C`；
2. 完全退出 WebRTC Client（关闭窗口），重新运行 `isaacsim-webrtc-streaming-client`，再填 `192.168.18.72 / 49100 / 47998 / 1280x720` 并连接；不要复用服务端尚未启动时产生的 6 次失败连接；
3. 在服务端的第二个 SSH 终端检查连接期间的端口与日志：

```bash
ss -lntp | grep ':49100' || true
ss -lunp | grep ':47998' || true
pgrep -af 'isaac-sim|kit/python' || true
```

4. 若客户端继续黑屏，而服务端日志已显示持续渲染，读取防火墙状态（只读）：

```bash
sudo ufw status verbose
sudo iptables -S INPUT
```

需要放行的最小范围是实验室内网来源到新主机的 TCP 49100 和 UDP 47998。先记录现有规则；未经确认不修改其他防火墙规则。

#### A-152.5：WebRTC UDP 媒体通道实测（待执行）

2026-09-11：服务端已确认 `kit` 监听 `0.0.0.0:49100`，客户端对 `192.168.18.72:49100` 的 TCP 测试成功。`iptables -S INPUT` 的基础策略为 `ACCEPT`，但 INPUT 仍跳转 KUBE 相关链；目前不能仅凭这一段规则断言 UDP 已通。

Isaac Sim 官方要求 WebRTC 同时具备 TCP `49100`（信令）和 UDP `47998`（媒体）。因此在服务端运行下面的只读抓包，保持 20 秒；随后立刻在客户端点击一次 Connect：

```bash
sudo timeout 20 tcpdump -ni any udp port 47998
```

同时在服务端另一个终端运行：

```bash
ss -lunp | grep ':47998' || true
```

结果解释：

| 抓包/端口结果 | 结论 | 下一步 |
|---|---|---|
| 出现来自客户端的 UDP 包，且 `ss` 出现 47998 | 网络已到达服务端；读取 Isaac 与 Client 最新日志，排查编码/协商 | 保存两端日志末尾 100 行 |
| 客户端点 Connect 时完全没有 UDP 包 | 到服务端的 UDP 被路径/主机规则阻断，或客户端未发起新协商 | 检查 `sudo ufw status verbose` 与 KUBE 链，不修改规则前先记录 |
| 有 UDP 入站但 `ss` 没有 Isaac `kit` 持有 47998 | 服务端没有创建媒体 socket | 检查是否已达到 `Isaac Sim Full Streaming App is loaded.`，确认只运行一个服务端 |

客户端主机 IP 用下列命令确定，不能把 Docker 或 VPN 地址当作放行来源：

```bash
ip route get 192.168.18.72
```

若确认 UFW 处于 active 且 UDP 被阻断，才考虑最小、可撤销的内网规则（将 `<client_lan_ip>` 替换为上一步的 `src` 地址）：

```bash
sudo ufw allow from <client_lan_ip> to any port 47998 proto udp comment 'Isaac Sim WebRTC media'
```

不要执行广泛的 `ufw disable`、清空 iptables 或修改 Kubernetes 链。

#### A-152.6：首次 UDP 抓包结果与下一次连接测试

2026-09-11：服务端执行 `sudo timeout 20 tcpdump -ni any udp port 47998`，终端显示 `0 packets captured`；随后 `ss -lunp | grep ':47998'` 无输出。该结果说明该 20 秒窗口内没有形成可观察的 WebRTC 媒体流，但**不能**用 `nc -vz ... 49100` 的成功替代 Client 连接成功：`nc` 只证明 TCP 信令端口可达，不会触发 WebRTC UDP 媒体协商。

下一轮必须按时间顺序操作：

```text
1. 服务端保持唯一 Isaac Streaming 实例运行。
2. 服务端另一个 SSH 终端启动 45 秒的行缓冲抓包。
3. 抓包开始后，完全退出并重新打开 Native WebRTC Client。
4. 填 192.168.18.72 / 49100 / 47998 / 1280x720，点击一次 Connect。
5. 45 秒结束后，同时保存抓包输出和客户端终端新增日志。
```

服务端抓包命令：

```bash
sudo timeout 45s tcpdump -l -ni any -vv 'udp port 47998'
```

`-l` 强制逐行输出，避免 `timeout` 结束时因输出缓冲看不到已经到达的数据。不要在没有“客户端重新点击 Connect”的同一时间窗口内据此修改防火墙。

#### A-152.7：两次无媒体包后的定位步骤

2026-09-11：第二次 45 秒、行缓冲抓包仍为 `0 packets captured`，所以当前不能将问题归为显存、GPU 或 Isaac 的 RTX 启动；服务端的 TCP 信令端口可达，但 WebRTC 媒体协商尚未完成。

先在**服务端**确认 Isaac 已完全加载。以下命令只读最近日志：

```bash
LOG=$(find "$HOME/.nvidia-omniverse/logs/Kit" -type f -name 'kit_*.log' \
  -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
echo "$LOG"
grep -Ei 'Streaming App is loaded|livestream|webrtc|49100|47998|fatal|error' "$LOG" | tail -n 120
```

然后在**客户端主机**确认它实际使用的出站 LAN 地址：

```bash
ip route get 192.168.18.72
```

输出中的 `src <client_lan_ip>` 才是抓包使用的地址。服务端随后执行（将示例地址换成该 src）：

```bash
sudo timeout 60s tcpdump -l -ni any -vv 'host <client_lan_ip> and udp'
```

抓包开始后，客户端完全退出、重新打开并点击 Connect 一次。保存两端证据：服务端抓包完整输出，以及客户端终端从 `Connecting to stream` 开始的最新 60 行。

解释：若能看到客户端任意 UDP 而目标不是 47998，说明协商使用了不同端口或配置没有生效；若仍无任意 UDP，Native Client 没有真正完成信令/开始 ICE，下一步读取 Client 日志而不是修改服务器防火墙。官方文档要求 TCP 49100 和 UDP 47998 均可达，且服务端必须已完全 loaded：[Livestream Clients](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/manual_livestream_clients.html)。

#### A-152.8：服务端 loaded 已确认，客户端源地址已确认

2026-09-11：服务端日志已出现：

```text
Isaac Sim Full Streaming App is loaded.
```

因此 Isaac Sim 6.0.1 服务端已准备完成，且持续渲染。日志中 `frame 47998`、`frame 49100` 是渲染帧序号，**不是**网络端口。

客户端主机对 `192.168.18.72` 的路由确认如下：

```text
192.168.18.72 dev eno1 src 192.168.18.154
```

服务端抓包命令必须直接使用 IP，不能复制 `<src ...>` 或任何尖括号占位符：

```bash
sudo timeout 60s tcpdump -l -ni any -vv 'host 192.168.18.154 and udp'
```

启动该命令后，立即在 `192.168.18.154` 上完全关闭并重新打开 Native Client，点击一次 Connect。抓包窗口结束后保存输出。

#### A-152.9：确认 UDP 未从客户端发出后的无修改网络测试

2026-09-11：服务端对 `host 192.168.18.154 and udp` 的 60 秒抓包仍为 `0 packets captured`。这表明在 Native Client 点击 Connect 的测试窗口内，没有任何 UDP 从客户端机器抵达新主机；尚不能通过修改新主机防火墙解决，因为包甚至未到达入口。

用一次单包 UDP 测试区分网络问题和 Client 协商问题。该操作不改配置、不停止 Isaac 服务、不发送任何机器人命令。

服务端先运行：

```bash
sudo timeout 20s tcpdump -l -ni any -vv 'host 192.168.18.154 and udp port 47998'
```

在它等待期间，客户端主机运行：

```bash
printf 'isaac-udp-test\n' | nc -u -w 1 192.168.18.72 47998
```

解释：

| 结果 | 结论 | 后续 |
|---|---|---|
| 服务端显示 `isaac-udp-test` 数据包 | 客户端到服务端的 UDP 路径正常；Native Client 未完成信令/ICE，收集其最新连接日志和服务端 WebRTC 日志。 |
| 服务端依旧没有包 | 客户端所在主机、交换网络或出口策略阻断 UDP；检查客户端主机的输出防火墙/网络策略，不能靠新主机入站规则修复。 |

上述测试完成后，再在客户端终端运行 Native Client 并保存一次新的完整连接日志：

```bash
isaacsim-webrtc-streaming-client 2>&1 | tee /tmp/isaac_webrtc_client.log
```

在 GUI 点击 Connect，等待六次尝试结束，再执行：

```bash
tail -n 100 /tmp/isaac_webrtc_client.log
```

#### A-152.10：UDP 路径验证通过，转入 Native Client 协商日志

2026-09-11：服务端抓包已收到：

```text
192.168.18.154.52966 > 192.168.18.72.47998: UDP, length 15
```

这是客户端用 `nc -u` 发送的测试包。因此客户端到新主机的 UDP 47998 路径、新主机网卡和入口策略均可用；不要添加 UFW 规则，也不要修改 Kubernetes/iptables 链。问题不在显存、Isaac 加载或通用 UDP 网络，而在 Native WebRTC Client 本身没有完成该次连接的信令/ICE。

下一步在客户端主机使用新日志运行 Client（服务端必须保持运行）：

```bash
rm -f /tmp/isaac_webrtc_client.log
isaacsim-webrtc-streaming-client 2>&1 | tee /tmp/isaac_webrtc_client.log
```

在 GUI 填写 `192.168.18.72`、`49100`、`47998`、`1280x720`，点击 Connect 并等待到成功或第六次失败。随后退出 Client，并执行：

```bash
tail -n 120 /tmp/isaac_webrtc_client.log
```

同时从服务端最新 Kit 日志取 WebRTC 相关行：

```bash
LOG=$(find "$HOME/.nvidia-omniverse/logs/Kit" -type f -name 'kit_*.log' \
  -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
grep -Ei 'webrtc|livestream|peer|offer|answer|ice|connect|error|fail' "$LOG" | tail -n 160
```

#### A-152.11：服务端与 Client 主机不要混用

2026-09-11：在新主机提示符 `tangyuan@tangyuan` 执行 `isaacsim-webrtc-streaming-client` 返回“未找到命令”，这是预期结果。该机器仅部署了 Isaac Sim 6.0.1 服务端；Native Client 已安装在旧主机/图形桌面 `tangyuan-System-Product-Name`（本轮路由源 IP `192.168.18.154`）。

主机职责固定如下：

```text
192.168.18.72  / tangyuan@tangyuan
  - 唯一的 isaac-sim.streaming.sh 服务端
  - 不能运行第二份服务端，也不需要 Native Client

192.168.18.154 / tangyuan-System-Product-Name
  - 图形桌面与 isaacsim-webrtc-streaming-client
  - Native Client 日志、Connect 操作和 UDP 测试从此主机发起
```

因此应在旧主机的本地图形终端执行：

```bash
rm -f /tmp/isaac_webrtc_client.log
isaacsim-webrtc-streaming-client 2>&1 | tee /tmp/isaac_webrtc_client.log
```

不要在新主机安装或启动第二个 Client 来代替远程桌面连接。

#### A-152.12：当前问题边界与最短路径

2026-09-11：当前双主机流媒体尚未成功显示。已确认的事实如下：

| 项目 | 结果 |
|---|---|
| Isaac Sim 6.0.1 服务端 | 已 loaded，持续渲染 |
| GPU/显存/启动 | 正常，不是当前阻塞点 |
| TCP 49100 | 客户端到服务端可达 |
| UDP 47998 通用路径 | 客户端 `nc -u` 测试包已到达服务端 |
| Native Client | 已启动，但还没有取得一次服务端运行期间的完整 Connect 结果日志 |

因此“把 Client 安装到新主机”不会自动修复问题；它只有在**能够直接使用新主机的图形桌面**时才有意义。SSH 终端没有 `DISPLAY`，即使安装 Client 也不能显示窗口。

最短的两条可行路线：

1. **保留现状（推荐）**：新主机只运行服务端，旧主机运行 Client；在 Client 窗口实际点击 Connect 后，保存从 `Connecting to stream` 开始的日志，以定位握手失败原因。
2. **同机查看**：先获得新主机图形桌面（物理显示器、受控的远程桌面会话或已有桌面会话），再在该桌面运行 Client，并让 Client 连接 `127.0.0.1`。这消除跨主机网络变量，但不是在 SSH 终端安装一个 `.deb` 就能完成。

#### A-152.13：Native Client 六次失败的服务端诊断

2026-09-11：客户端在服务端已 loaded 后进行的实际连接，于 `09:05:08` 开始，随后六次失败。日志没有细节，只能说明会话在 `Starting stream` 后立即失败。普通 UDP 测试已通过，故不再重复网络/防火墙测试。

在**新主机服务端**执行以下一条只读命令，提取同一实例的会话、NVENC/StreamingSDK 与 WebRTC 错误：

```bash
LOG=$(find "$HOME/.nvidia-omniverse/logs/Kit" -type f -name 'kit_*.log' \
  -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
echo "LOG=$LOG"
grep -Ein '09:05|webrtc|livestream|streamsdk|nvst|signaling|processing.*header|session|peer|offer|answer|ice|nvenc|encode|fatal|error|failed' "$LOG" | tail -n 240
```

典型的决定性证据包括 `Processing ... signaling headers`、`Failed to create video stream`、`StreamSdkException`、`NVST_*`。只有出现这些行后，才选择修复视频编码会话或候选地址；不要凭客户端“六次失败”盲目重装 Isaac 或改变防火墙。

#### A-152.14：服务端日志没有会话事件，直接抓信令 TCP

2026-09-11：服务端提供的日志片段仅有 `omni.usd.multitick.render` 渲染循环，未出现 `Processing signaling headers`、WebRTC peer、StreamSDK 或编码错误。该片段不能说明视频会话已进入服务端。

下一步不再用宽泛 `grep`，直接抓真实 TCP 信令。服务端运行：

```bash
sudo timeout 75s tcpdump -l -ni any -vv 'host 192.168.18.154 and tcp port 49100'
```

在抓包启动后，客户端完全退出再重开，填正确的纯 IP `192.168.18.72`（不要填写 `http://`、`https://` 或 `:49100`），端口仍分填 `49100` 与 `47998`，点击一次 Connect。

结果：

| 抓包结果 | 结论 |
|---|---|
| 出现来自 `192.168.18.154` 的 TCP SYN/数据包 | Native Client 已触达信令服务；再按时间截取服务端日志的 WebRTC 行。 |
| 没有任何 TCP 包 | Client GUI 没有使用该地址、没有真正触发连接，或客户端本机策略阻止 Electron；优先检查 GUI Server 字段和 Client 日志。 |

`nc` 的独立探测不作为 Native Client 已发起信令的证据。

#### A-152.15：Native Client 未到达服务端时排除本机代理

2026-09-11：在 Client 点击 Connect 的诊断窗口中，服务端仍未看到来自 `192.168.18.154` 到 TCP 49100 的流量；但同一客户端主机 `nc` 能直连该端口。这是**推断**：Electron Native Client 可能继承了 HTTP/SOCKS 代理或系统代理设置，令其连接未直接发往内网服务端。

先完全关闭 Native Client；在客户端主机（`tangyuan-System-Product-Name`）执行以下临时环境命令。它只影响本次进程，不写入 shell 配置或系统配置：

```bash
env -u http_proxy -u https_proxy -u all_proxy -u no_proxy \
    -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY \
    isaacsim-webrtc-streaming-client --no-proxy-server 2>&1 \
    | tee /tmp/isaac_webrtc_client_noproxy.log
```

在打开的窗口重填纯 IP `192.168.18.72` 与端口 `49100`、`47998` 后点击 Connect。若成功，说明问题就是 Client 代理路径；若仍失败，再运行以下只读检查并记录结果：

```bash
env | grep -iE '(^|_)(http|https|all|no)_proxy=' || true
gsettings get org.gnome.system.proxy mode 2>/dev/null || true
```

不要修改新主机的防火墙、Kubernetes 规则或 Isaac 安装。

#### A-152.16：无代理失败后的并发信令抓包（决定性测试）

2026-09-11：以 `--no-proxy-server` 和清空代理环境变量启动 Native Client 后，仍在启动后约 6 ms 进入重试，因此本机代理假设已排除。

此前前台抓包与 GUI 点击的时间窗口无法从输出确认。改用后台抓包，一次记录 TCP 信令和 UDP 媒体，避免等待抓包结束后才点 Connect。

**在新主机执行后立刻切换到旧主机，不要等待命令结束：**

```bash
rm -f /tmp/isaac_webrtc_wire.log
sudo timeout 90s tcpdump -l -ni any -vv \
  'host 192.168.18.154 and (tcp port 49100 or udp port 47998)' \
  > /tmp/isaac_webrtc_wire.log 2>&1 &
echo "capture_pid=$!"
```

**随后立刻在旧主机**关闭旧 Client，再用无代理命令启动、填写纯 IP 并点击一次 Connect：

```bash
env -u http_proxy -u https_proxy -u all_proxy -u no_proxy \
    -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY \
    isaacsim-webrtc-streaming-client --no-proxy-server
```

等待 90 秒后，新主机执行：

```bash
cat /tmp/isaac_webrtc_wire.log
```

| wire 日志 | 结论 |
|---|---|
| 没有 TCP 49100 包 | Client 进程没有向填入的服务端地址建立信令，重点检查 Client 配置/进程状态。 |
| 有 TCP 49100 但没有 UDP 47998 | 信令服务或服务端会话拒绝，按时间读取 Kit 中 `streamsdk/NVST/signaling` 行。 |
| TCP 和 UDP 都有 | 网络与握手已完成，问题转为服务端视频编码或 Client 渲染，读取编码错误。 |

#### A-152.17：服务端 wire 日志为空，改在 Client 本机捕获真实目标

2026-09-11：后台 90 秒服务端 wire 日志只有 tcpdump 启动信息，没有来自 `192.168.18.154` 的 TCP 49100 或 UDP 47998。这证明当前 Native Client 的失败请求没有抵达新主机；不能继续修改服务端、端口或防火墙。

Native Client 日志只打印端口，不打印实际目标地址。改在旧主机 (`tangyuan-System-Product-Name`) 本地抓取全部相关出站流量：

```bash
rm -f /tmp/isaac_webrtc_client_wire.log
sudo timeout 90s tcpdump -l -ni any -vv \
  '(tcp port 49100 or udp port 47998)' \
  > /tmp/isaac_webrtc_client_wire.log 2>&1 &
echo "capture_pid=$!"
```

该命令启动后，在同一旧主机的 WebRTC Client 窗口点击一次 Connect；90 秒后执行：

```bash
cat /tmp/isaac_webrtc_client_wire.log
```

结果用于直接定位：

| Client 本机抓包结果 | 意义 |
|---|---|
| 目标为 `192.168.18.72` | 包在旧主机发出但未到服务端，检查中间网络/路由。 |
| 目标为 `127.0.0.1`、Docker/VPN 地址或其他 IP | GUI 配置未被实际使用或 Client 保存了错误配置；备份并重置 Client 用户配置。 |
| 完全没有 49100/47998 流量 | Client 进程未真正提交连接；检查其用户配置和应用启动状态。 |

#### A-152.18：后台 tcpdump 的 sudo 密码处理

2026-09-11：将 `sudo tcpdump ... &` 直接放到后台会使 sudo 无法从终端读取密码，job 会显示“已停止”；之后输入的密码会被 shell 误当成命令。这不是 tcpdump 或网络错误。

必须先在前台缓存 sudo 凭据，再启动后台抓包：

```bash
sudo -v
rm -f /tmp/isaac_webrtc_client_wire.log
sudo timeout 90s tcpdump -l -ni any -vv '(tcp port 49100 or udp port 47998)' \
  > /tmp/isaac_webrtc_client_wire.log 2>&1 &
echo "capture_pid=$!"
```

看到 `capture_pid=...` 后不要等待命令结束，立刻在 Client 窗口点击 Connect；90 秒后再 `cat /tmp/isaac_webrtc_client_wire.log`。

#### A-152.19：Client 本机无任何 socket 流量，备份并重置用户配置

2026-09-11：Client 本机 90 秒抓包只有 tcpdump 启动信息，没有 TCP 49100 或 UDP 47998，连 loopback 都没有。结合 Client 控制台的“attempts failed”，可确定失败发生在 Native Client 建立 socket **之前**；新主机、路由、防火墙与 Isaac Sim 服务端不再是当前原因。

下一步备份（不删除）Native Client 的 Electron 用户配置，并用全新配置启动。先完全退出所有 WebRTC Client 窗口，再在旧主机执行：

```bash
CLIENT_CFG="$HOME/.config/Isaac Sim WebRTC Streaming Client"
CLIENT_BAK="${CLIENT_CFG}.backup_$(date +%Y%m%d_%H%M%S)"

if [ -e "$CLIENT_CFG" ]; then
  mv "$CLIENT_CFG" "$CLIENT_BAK"
  echo "backup=$CLIENT_BAK"
fi

env -u http_proxy -u https_proxy -u all_proxy -u no_proxy \
    -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY \
    isaacsim-webrtc-streaming-client --no-proxy-server
```

新窗口重新填写纯 IP `192.168.18.72`、Signal `49100`、Stream `47998`、分辨率 `1280x720`，再点击 Connect。配置已备份，可用下列命令恢复：

```bash
rm -rf "$CLIENT_CFG"
mv "$CLIENT_BAK" "$CLIENT_CFG"
```

恢复命令只在明确需要回退时执行。

#### A-152.20：更正“Client 未建 socket”的结论，改测 WebSocket 信令端点

2026-09-11：此前 Client 本机 tcpdump 为空，不能单独证明 Client 没有创建 socket；抓包和 GUI 点击可能未严格重叠。检查 Client 本地持久化数据已找到它使用的正确地址：

```text
ws://192.168.18.72:49100/sign_in?peer-id=&version=2
```

因此不再围绕 ping/IP 猜测。必须直接验证该 WebSocket 信令端点：正常情况应返回 `HTTP/1.1 101 Switching Protocols`。

先在新主机确认服务仍在：

```bash
ss -lntp | grep ':49100' || true
pgrep -af 'isaac-sim|kit' || true
```

再在旧主机运行手工 WebSocket Upgrade 请求：

```bash
curl -isS --max-time 5 --http1.1 \
  -H 'Connection: Upgrade' \
  -H 'Upgrade: websocket' \
  -H 'Sec-WebSocket-Version: 13' \
  -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
  'http://192.168.18.72:49100/sign_in?peer-id=&version=2'
```

| 返回 | 含义 | 后续 |
|---|---|---|
| `101 Switching Protocols` | 信令端点正常；再解决 Native Client 进程/配置。 |
| `Connection refused` / timeout | 服务端停止或端口并非当前 Streaming 实例。 |
| `400/404/非 101` | 服务端已监听但并非正确的 Isaac WebRTC 信令状态，检查服务端启动命令和同时间的 Kit 日志。 |

这项检查替代继续 ping 或反复抓包。

#### A-152.21：最终根因——目标主机 49100 当前未监听

2026-09-11：在旧主机执行 WebSocket Upgrade 请求得到：

```text
curl: (7) Failed to connect to 192.168.18.72 port 49100 ... Couldn't connect to server
```

这比 ping、UDP 和 Client 日志更直接：目标新主机 `192.168.18.72` 当前没有运行/监听 WebRTC 信令服务。之前在旧主机执行的 `pgrep` 输出包含 `/home/tangyuan/zitian/software/isaacsim-6.0.1/.../omni.telemetry.transmitter`，它是**旧主机**上的遥测子进程/残留，不是目标新主机的 Streaming 服务，不能作为服务存活证据。

从旧主机先 SSH 到目标主机：

```bash
ssh tangyuan@192.168.18.72
hostname
hostname -I
```

确认目标为 `192.168.18.72` 后，在该 SSH 会话中用 nohup 启动唯一服务端；这样即使 SSH 会话随后断开，服务也不会因 SIGHUP 停止：

```bash
IS6="$HOME/isaacsim-6.0.1"
LOGDIR="$HOME/isaacsim-streaming-logs"
mkdir -p "$LOGDIR"

nohup env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
  -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  "$IS6/isaac-sim.streaming.sh" \
  --/exts/omni.kit.livestream.app/primaryStream/publicIp=192.168.18.72 \
  --/exts/omni.kit.livestream.app/primaryStream/signalPort=49100 \
  --/exts/omni.kit.livestream.app/primaryStream/streamPort=47998 \
  > "$LOGDIR/streaming_$(date +%Y%m%d_%H%M%S).log" 2>&1 &

echo "isaac_pid=$!"
```

约 30 秒后仍在目标主机执行：

```bash
ss -lntp | grep ':49100'
pgrep -af 'isaac-sim|kit/python' | head -20
```

只有看到 `0.0.0.0:49100` 被目标主机上的 `kit` 监听后，才回旧主机启动 Native Client。不要把 `pgrep` 检查误在旧主机执行。

#### A-152.22：Streaming 服务已稳定后台启动

2026-09-11：目标新主机启动命令返回 `isaac_pid=1764271`，并已验证：

```text
LISTEN ... 0.0.0.0:49100 ... users:(("kit",pid=1764271,...))
```

此前 Client 六次失败的直接原因是该目标端口当时未监听；当前服务以 nohup 运行，不会因 SSH 终端关闭而自动停止。

下一步在新主机确认 loaded（约等 30 秒）：

```bash
LOG=$(ls -t "$HOME"/isaacsim-streaming-logs/streaming_*.log | head -1)
echo "$LOG"
grep -F 'Isaac Sim Full Streaming App is loaded.' "$LOG" || tail -n 30 "$LOG"
```

出现 loaded 后，在旧主机运行 Native Client，填 `192.168.18.72 / 49100 / 47998 / 1280x720`，点击 Connect。服务端继续在后台运行，无需保持原 SSH 窗口。

### A-153：将 OpenArm URDF 首次导入 Isaac Sim 6.0.1

2026-09-11：Streaming 端已启动后，第一步只导入**未补偿的原始双臂模型**，生成 USD 资产。该步骤离线进行：不启动 ROS Bridge、不连接旧主机的 CAN 或真机控制器，也不发送任何真机命令。

现有参考模型为 `alignment/openarm_v20_reference.urdf`。它包含完整双臂、夹爪、碰撞网格和关节限位，但网格使用 ROS 的 `package://openarm_description/...` URI。Isaac 的 GUI 导入器不应依赖当前 ROS 环境，因此先生成一份把 URI 转为本机 `file://` 绝对路径的副本。原 URDF 不被修改。

#### 1. 在 **新主机** 的 SSH 终端生成 Isaac 导入副本

```bash
cd ~/openarm_ws
chmod +x alignment/prepare_isaacsim_urdf.sh
bash alignment/prepare_isaacsim_urdf.sh
```

预期最后输出：

```text
Import this file in the Isaac Sim GUI:
  /home/tangyuan/openarm_ws/alignment/isaacsim_assets/openarm_v20_import/openarm_v20_isaac.urdf
Suggested USD output directory:
  /home/tangyuan/openarm_ws/alignment/isaacsim_assets/openarm_v20_import
```

这个命令仅写入以下新目录：

```text
alignment/isaacsim_assets/openarm_v20_import/
  openarm_v20_isaac.urdf
  openarm_v20.usd                  # GUI 导入后生成
```

若脚本报 `Missing description assets`，说明新主机的工作区没有完整迁移 `src/openarm_description`；此时先迁移该目录，不能用缺网格的 URDF 继续导入。

#### 2. 在 Isaac Sim Streaming 界面导入

1. 打开 **Window → Extensions**，搜索并启用 `isaacsim.asset.importer.urdf`。若菜单已出现 URDF Importer，则不需重复启用。
2. 打开 **File → Import**，选择 `URDF`；在远程文件选择框中填入：

   ```text
   /home/tangyuan/openarm_ws/alignment/isaacsim_assets/openarm_v20_import/openarm_v20_isaac.urdf
   ```

3. USD 输出位置选择：

   ```text
   /home/tangyuan/openarm_ws/alignment/isaacsim_assets/openarm_v20_import/openarm_v20.usd
   ```

4. 首次导入采用以下设置，以保留可核对的连杆和关节结构：

   | 设置 | 首次导入值 | 原因 |
   |---|---|---|
   | Fix Base / 固定基座 | 开启 | 防止机器人在空场景中受重力下落。 |
   | Merge Fixed Joints | 关闭 | 保留 URDF 链路层次，方便核对双臂和夹爪。 |
   | Merge Meshes | 关闭 | 网格问题可定位到单个 link；验证后再优化。 |
   | Collision From Visuals | 关闭 | URDF 已提供单独 collision STL。 |
   | Self Collision | 首次关闭 | 先排除初始自碰撞；模型验证后再单独启用。 |

5. 点击 **Import**。等待输出窗口完成；随后保存 stage。导入器已写 USD 时，不需要把偏差补偿手工写入该 USD。

#### 3. 首次验证（只在仿真中）

在 Stage 中展开新 Articulation，确认至少能看到以下 14 个臂关节；夹爪关节可随后单独核对：

```text
openarm_left_joint1 ... openarm_left_joint7
openarm_right_joint1 ... openarm_right_joint7
```

检查以下项目后，在此处填写：

| 验证项 | 结果 | 证据/备注 |
|---|---|---|
| URDF 导入完成且无 missing mesh | `[ ]` | `________________` |
| 左右 14 个臂关节均可见 | `[ ]` | `________________` |
| 关节名称、正方向和限位与 URDF 一致 | `[ ]` | `________________` |
| 固定基座且静止时未下落/爆炸 | `[ ]` | `________________` |
| USD 保存路径 | `[ ]` | `________________` |

首次验证通过后，再建立 Isaac 的 action/replay 映射层。此前记录的固定 offset 和 J5/J6 方向相关补偿只能在 **比较层或 replay 输入变换层**加载；不要现在直接改原始 URDF 的 `origin`、`axis`、限位或真机反馈。

### A-154：优先从厂家 MuJoCo 模型快速迁移到 Isaac Sim

2026-09-11：厂家当前使用 MuJoCo，因此首轮迁移的最短路径是 Isaac Sim 6.0.1 的 **MJCF Importer**，而不是先把 MJCF 手工重写为 URDF。厂家模型位于其 `openarm_mujoco` 包的 `share/openarm_mujoco/v2/` 下：

```text
v2/
  openarm_bimanual.xml       # 左右机械臂、夹爪、执行器、质量、惯量和关节限位
  assets/                    # OBJ/STL 网格
  cell/cell.xml              # 双臂、升降轴、工作台、碰撞体和相机定义
  cell/demo.xml              # cell 场景加演示方块/框架
```

`cell/cell.xml` 是第一份应导入的文件：它已经通过 `<attach>` 引入双臂模型，并保留厂家使用的相对网格路径。URDF 仍保留给 ROS/工具链使用，但不作为最快的厂家 MuJoCo 场景迁移路径。

#### 1. 在新主机快照厂家 MJCF 资产

新主机的 `openarm_ws` 是早期迁移版本，可能还没有本 README 新增的辅助脚本。先从旧主机只复制这个很小的脚本；这不会重新传输数据集、模型权重或 Isaac 安装包：

```bash
# 在旧主机（192.168.18.154）执行
scp ~/openarm_ws/alignment/prepare_mujoco_to_isaac.sh \
  tangyuan@192.168.18.72:/home/tangyuan/openarm_ws/alignment/
```

再在新主机执行：

```bash
cd ~/openarm_ws
chmod +x alignment/prepare_mujoco_to_isaac.sh
bash alignment/prepare_mujoco_to_isaac.sh
```

本次执行结果（2026-09-14）：

```text
Vendor MuJoCo v2 source: /home/tangyuan/openarm_ws/dora/dora-openarm-data-collection/.venv/share/openarm_mujoco/v2
Isaac import snapshot:    /home/tangyuan/openarm_ws/alignment/isaacsim_assets/mujoco_v2
First MJCF to import:     /home/tangyuan/openarm_ws/alignment/isaacsim_assets/mujoco_v2/cell/cell.xml
Optional demo scene:      /home/tangyuan/openarm_ws/alignment/isaacsim_assets/mujoco_v2/cell/demo.xml
```

快照已成功生成；下一步在 Isaac Sim 的 **File → Import** 中选择：

```text
/home/tangyuan/openarm_ws/alignment/isaacsim_assets/mujoco_v2/cell/cell.xml
```

该命令只复制厂家 `v2` 目录到工作区的稳定快照：

```text
alignment/isaacsim_assets/mujoco_v2/
```

它不会改动厂家 `.venv/share/openarm_mujoco/v2` 中的源文件。若脚本提示找不到 `share/openarm_mujoco/v2/cell/cell.xml`，先在新主机确认源包是否已经迁移：

```bash
find ~/openarm_ws/dora -type f \
  -path '*/share/openarm_mujoco/v2/cell/cell.xml' -print
```

没有结果时，从旧主机复制完整厂家资产目录（只复制仿真资产，不复制整个虚拟环境）：

```bash
# 在旧主机执行；SRC 的实际路径以 find 输出为准
SRC=~/openarm_ws/dora/dora-openarm-data-collection/.venv/share/openarm_mujoco
rsync -aH --info=progress2 "$SRC/" \
  tangyuan@192.168.18.72:/home/tangyuan/openarm_ws/dora/dora-openarm-data-collection/.venv/share/openarm_mujoco/
```

#### 2. 在 Isaac Sim 导入厂家 MJCF

1. 在 Streaming 界面打开 **Window → Extensions**，启用 `isaacsim.asset.importer.mjcf`。
2. 选择 **File → Import**，文件选：

   ```text
   /home/tangyuan/openarm_ws/alignment/isaacsim_assets/mujoco_v2/cell/cell.xml
   ```

3. USD 输出位置设为：

   ```text
   /home/tangyuan/openarm_ws/alignment/isaacsim_assets/openarm_cell_from_mjcf.usd
   ```

4. 首次导入设置：保留网格和独立碰撞体（`Merge Mesh` 关闭、`Collision From Visuals` 关闭）。模型根没有 free joint，保持默认静态基座设置即可。
5. 点击 **Import**，并在 Output Log 检查是否出现 missing mesh、unsupported tag 或 joint-name replacement。

验证 `cell.xml` 后，再单独导入 `mujoco_v2/cell/demo.xml` 来迁移演示方块和黑色框架。不要在同一个 stage 内重复导入 `cell.xml` 和 `demo.xml`，否则工作台和双臂会重复出现。

#### 3. 迁移范围与后续工作

MJCF Importer 可直接带入：机器人和场景几何、相对位姿、关节轴/限位、质量、惯量、可视/碰撞网格，以及 MuJoCo 已定义的基础摩擦和执行器数据。Isaac 6.0 使用其自身的物理和执行器实现，因此以下项目不能视为“已对齐”：

| 项目 | 迁移后状态 | 后续做法 |
|---|---|---|
| MuJoCo `position kp/kv`、力矩限制、阻尼/摩擦 | 参数可读入，动态响应不会自动等价 | 在 Isaac 中按单关节 replay 重标定。 |
| `solref`、`solimp`、椭圆摩擦锥 | 不能直接等价 Isaac 接触解算器 | 用抓取/插入 replay 校准接触材料和接触参数。 |
| 五路相机与视觉外观 | 基础 camera pose 可作参考，图像不等价 | 按 A-110 重新核对内外参、分辨率、光照和时间戳。 |
| DORA/MuJoCo ROS 节点、策略运行时 | 不会随 USD 转换 | 新建 Isaac replay adapter，复用 action/observation schema。 |
| 固定 offset、J5/J6 方向补偿 | 不写入 MJCF/URDF/USD 原始模型 | 作为 replay 的 input/compare transform 层加载。 |

完成导入后先做一个 `home` 姿态静态截图和 14 个臂关节名称核对，再在 Isaac Sim 内重新生成一条 Isaac-native action episode。历史 MuJoCo action parquet 不作为当前 replay 输入；不要直接把 MuJoCo 控制器增益、真机反馈或 DORA bridge 接到 Isaac 模型。

#### A-154.1：`cell.xml` 首次转换异常时的降级导入

`cell/cell.xml` 使用 MuJoCo 的嵌套模型结构：它通过 `<model file="../openarm_bimanual.xml">` 和 `<attach>` 组合双臂、升降轴和工作区。如果 Isaac 的 MJCF Importer 报 `Failed to convert assets due to unknown exception`，先不把它归因为 GPU/显存问题；启动后的 GPU 余量与该 XML 转换异常无关。

先在同一份 `mujoco_v2` 快照中直接导入厂家双臂模型：

```text
/home/tangyuan/openarm_ws/alignment/isaacsim_assets/mujoco_v2/openarm_bimanual.xml
```

它保留双臂、夹爪、网格、关节限位、质量、惯量、阻尼和执行器定义，但暂时不含 `cell.xml` 的升降轴和工作台。通过这个导入先验证机器人资产路径；随后再将 cell 工作区作为单独 USD/手工场景迁移，避免在同一次转换中混合定位机器人、嵌套 attach 与环境的问题。

在新主机采集失败原始信息：

```bash
LOG=$(ls -t "$HOME"/isaacsim-streaming-logs/streaming_*.log | head -1)
echo "$LOG"
grep -nEi 'mjcf|cell\.xml|openarm|error|exception|traceback|failed' "$LOG" | tail -120
```

将该输出填入：

```text
导入文件: ______________________________
异常首行: ______________________________
直接导入 openarm_bimanual.xml: [ ] 成功  [ ] 失败
```

#### A-154.2：MJCF 导入器连续失败后的可执行迁移路径

本轮 `cell.xml` 和 `openarm_bimanual.xml` 都在 Isaac 的 MJCF 转 USD 阶段报同一条泛化异常。此时停止尝试不同 MJCF 文件；问题尚未有 traceback 前不能安全判断为某一个厂家参数，也不应继续修改厂家 XML。

改用 Isaac Sim 官方的 URDF→USD 路径导入同一份 OpenArm v2 描述。URDF 源位于工作区 `src/openarm_description`，使用同一套 DAE/STL 网格、双臂链路、夹爪、质量、惯量、轴和限位。以下命令在**新主机**直接执行，不依赖本 README 新增脚本：

```bash
cd ~/openarm_ws

SRC="$HOME/openarm_ws/src/openarm_description/assets/robot/openarm_v2.0/urdf/example/v2.urdf"
DESC="$HOME/openarm_ws/src/openarm_description"
OUT="$HOME/openarm_ws/alignment/isaacsim_assets/openarm_v20_urdf"

test -f "$SRC" && test -d "$DESC/assets" || {
  echo 'OpenArm URDF/mesh assets are missing from this host'; exit 1;
}

mkdir -p "$OUT"
sed "s|package://openarm_description/|file://$DESC/|g" "$SRC" \
  > "$OUT/openarm_v20_isaac.urdf"

ls -lh "$OUT/openarm_v20_isaac.urdf"
```

之后在 Isaac Sim：

1. `Window → Extensions` 启用 `isaacsim.asset.importer.urdf.ui`；
2. `File → Import`；
3. 在文件选择栏输入：

   ```text
   file:///home/tangyuan/openarm_ws/alignment/isaacsim_assets/openarm_v20_urdf/openarm_v20_isaac.urdf
   ```

4. USD Output 设为：

   ```text
   /home/tangyuan/openarm_ws/alignment/isaacsim_assets/openarm_v20_urdf/openarm_v20.usd
   ```

5. 首次导入：`Fixed`、`Merge Mesh` 关闭、`Collision From Visuals` 关闭、`Self Collision` 关闭；点击 Import。

这是本阶段的迁移结论：USD 机器人资产使用 URDF 路径生成；MuJoCo `cell.xml` 的桌面、演示方块和相机配置随后根据其数值单独添加到 Isaac 场景。MuJoCo 的控制增益、接触求解器和补偿层不会随 URDF 自动迁移，仍按 replay 对齐。

### A-155：Isaac Sim 启动命令和 `intern_data_engine` 框架评估

#### 1. 当前 Isaac Sim 启动脚本

新主机上使用 6.0.1 时，把安装目录明确传给脚本。脚本会隔离 ROS/conda 环境，并打开 WebRTC Streaming 服务；它不会启动真机 bringup，也不会连接 CAN：

```bash
cd ~/openarm_ws
chmod +x alignment/start_isaacsim_streaming.sh
ISAAC_ROOT="$HOME/isaacsim-6.0.1" \
ISAAC_PUBLIC_IP=192.168.18.72 \
bash alignment/start_isaacsim_streaming.sh
```

如果新主机实际路径是 `~/isaacsim`，只改第一行变量：

```bash
ISAAC_ROOT="$HOME/isaacsim" ISAAC_PUBLIC_IP=192.168.18.72 \
  bash alignment/start_isaacsim_streaming.sh
```

启动后在新主机检查：

```bash
ss -lntp | grep ':49100'
pgrep -af 'isaac-sim|kit/python' | head -20
```

旧主机的 WebRTC Client 填 `192.168.18.72`、Signal `49100`、Stream `47998`。如果只需要新主机本地 GUI，不走 WebRTC：

```bash
cd ~/openarm_ws
ISAAC_ROOT="$HOME/isaacsim-6.0.1" bash alignment/start_isaacsim_clean.sh
```

上述两个脚本已放在 `alignment/`，因此需要从旧主机同步到新主机时只复制脚本文件即可：

```bash
scp ~/openarm_ws/alignment/start_isaacsim_streaming.sh \
  tangyuan@192.168.18.72:/home/tangyuan/openarm_ws/alignment/
scp ~/openarm_ws/alignment/start_isaacsim_clean.sh \
  tangyuan@192.168.18.72:/home/tangyuan/openarm_ws/alignment/
```

#### 2. 已检查的内部仓库版本

仓库地址：`http://192.168.18.200:53000/EmbodiedAI/intern_data_engine.git`。

```text
master    c294de38e8644c4fadaf10e5326d665de9dbfd7e
new_branch 16031fdc51381c9d803188b5af0acb2708e91699
```

本次按需求检查的是 `new_branch`，临时检出目录为 `/tmp/intern_data_engine_review`；没有把它混入当前 OpenArm 工作区。若要在新主机保存一份可追溯副本：

```bash
cd ~/openarm_ws
mkdir -p third_party
git clone --branch new_branch \
  http://192.168.18.200:53000/EmbodiedAI/intern_data_engine.git \
  third_party/intern_data_engine
git -C third_party/intern_data_engine checkout 16031fdc51381c9d803188b5af0acb2708e91699
```

#### 3. 能复用的部分

| 模块 | 发现 | 对 OpenArm 的用法 |
|---|---|---|
| `workflows/simbox_dual_workflow.py` | 已有双臂 workflow 的 `reset`、`generate_seq`、`seq_replay`、`save` | 作为 OpenArm replay workflow 的骨架。 |
| `workflows/simbox/core/robots/template_robot.py` | 统一处理左右关节索引、夹爪、末端位姿和 observation | 新增 `OpenArm` 类，填入 7+7 关节及夹爪索引。 |
| `workflows/simbox/core/controllers/template_controller.py` | 控制器可按 robot YAML 的关节索引和 URDF/CuRobo 配置工作 | 新增 OpenArm 控制器；先支持位置 action，不接真机。 |
| `workflows/simbox/core/cameras/custom_camera.py`、`core/utils/camera_utils.py` | 支持 RGB、深度、分割、bbox、相机参数和 `camera2env_pose` 输出 | 使用已有五路相机名称和 A-110 标定值建立 Isaac 相机配置。 |
| `workflows/simbox/core/loggers/lmdb_logger.py` | 保存每帧 state/action/image 并导出 LeRobot 格式 | 增加 OpenArm parquet→内部 frame schema 的适配器。 |
| `nimbus/`、`nimbus_extension/` | 规划、渲染、存储、调度的批处理框架 | 单条 replay 通过后再接入；首轮 gap 不需要 Nimbus 调度。 |

#### 4. 当前不能直接复用的部分

仓库现成 robot 配置主要是 SO101、Split Aloha、Lift2、Genie1、Franka；没有 `openarm_v20` 配置、OpenArm USD 注册、OpenArm 14-DOF action schema 或真机 gap comparator。现有 `scripts/import_so101_urdf_to_usd.py` 还使用旧的 `URDFParseAndImportFile` 命令，而 Isaac Sim 6 已移除该调用；OpenArm 应使用已经成功生成的 USD，或改用 `URDFImporter`/`URDFImporterConfig` API。

仓库的 `tests/integration/data_comparators/simbox_comparator.py` 也不是本项目的 sim2real comparator：它要求两边都是 InternDataEngine 输出目录（`meta_info.pkl` + `lmdb/`），并按 LMDB 类别比较数值和图像。它不能直接把 `alignment/results/*summary.csv`、ROS bag 或真机反馈转成可比较输入；其中默认 `tolerance=1e-6` 也不适合把真实控制噪声当成零误差。我们可以复用它的输出检查思路，但关节 RMSE、固定误差、方向误差、延迟和同步指标仍使用 `alignment` 的字段和脚本。

代码还大量导入 `omni.isaac.core`，并有写死 Isaac 5.1 路径的脚本。正式接入 Isaac 6 前需先完成 API 兼容性检查；不要直接运行仓库的 SO101 示例来判断 OpenArm 是否可用。

因此结论是：这个库适合复用“Isaac 场景加载、双臂 workflow、相机采集、轨迹 replay、数据记录”层；不适合直接复用为 OpenArm 的 sim2real 对齐工具。我们需要写一个很薄的 OpenArm adapter，接口只做四件事：

```text
OpenArm USD/关节名  <->  InternDataEngine robot config
MuJoCo/真机 parquet <->  workflow frame/action schema
Isaac joint state   ->   与 alignment/results 的比较字段
固定/方向 offset    ->   replay input/compare transform（不改原始 USD）
```

#### 5. 在开始新的 gap 前必须完成的三项

| 顺序 | 工作 | 证据 |
|---:|---|---|
| 1 | 在 Isaac 中保存已成功打开的 OpenArm USD，并导出/记录 14 个臂关节和夹爪关节的实际 prim/joint 顺序 | `________________` |
| 2 | 从 `intern_data_engine` 复制 `template_robot`、`template_controller` 和 `SimBoxDualWorkFlow` 的最小依赖，新增 OpenArm YAML，不运行现成 SO101 配置 | `________________` |
| 3 | 在 Isaac Sim 内重新生成一条 Isaac-native 单臂/双臂 action episode，只输出 sim joint states、TF 和相机帧；确认时间戳、单位和关节顺序后再做 sim2real gap | `________________` |

只有第 3 项 replay 通过，才开始重新采集或比较新的 sim2real gap。这样可以把“模型导入错误”“框架关节顺序错误”和“真实 sim2real 偏差”分开记录。

#### 6. 本轮验收填写

```text
Isaac 安装根目录: ______________________
Isaac 版本（VERSION）: __________________
OpenArm USD 路径: ______________________
InternDataEngine 分支/commit: new_branch / 16031fdc51381c9d803188b5af0acb2708e91699
是否存在 OpenArm robot YAML: [ ] 是  [ ] 否
是否存在 OpenArm replay adapter: [ ] 是  [ ] 否
SimBoxComparator 是否直接支持真机 CSV: [ ] 是  [ ] 否
首次 Isaac 离线 replay 输出: ____________
```

### A-156：49100 已被旧 Isaac 实例占用时的处理

`ss` 显示 `0.0.0.0:49100` 正在监听，表示本机已经有一个 Isaac Streaming 服务占用了信令端口。此时不要再次运行启动脚本；先判断它是否就是当前使用的 Isaac Sim 6.0.1。下面命令必须在运行 Isaac Sim 的**新主机**终端执行，不能在旧主机或 WebRTC Client 所在终端执行。

#### 1. 找到占用端口的 PID 并核对

```bash
PORT_PID=$(ss -lntpH | awk '$4 ~ /:49100$/ {
  match($0, /pid=[0-9]+/)
  if (RSTART) { print substr($0, RSTART + 4, RLENGTH - 4); exit }
}')

if [ -z "$PORT_PID" ]; then
  echo "49100 当前没有监听，旧实例可能已经退出"
else
  echo "49100 PID=$PORT_PID"
  ps -o user,pid,ppid,pgid,etime,stat,cmd -p "$PORT_PID"
  echo "cwd=$(readlink -f "/proc/$PORT_PID/cwd" 2>/dev/null || true)"
  echo "exe=$(readlink -f "/proc/$PORT_PID/exe" 2>/dev/null || true)"
  printf 'cmdline='
  tr '\0' ' ' < "/proc/$PORT_PID/cmdline" 2>/dev/null || true
  echo
fi
```

确认输出中的用户是当前账号，且 `cwd`、`exe` 或 `cmdline` 指向 `isaacsim-6.0.1`。如果 PID 在 `ps` 中不存在，重新执行一次 `ss`；这是进程刚好退出或当前终端不是同一台主机造成的竞态，不要根据旧 PID 执行 `kill`。

#### 2. 判断结果

| 核对结果 | 操作 |
|---|---|
| PID 是当前账号的 Isaac Sim 6.0.1 | 直接复用该实例，在 WebRTC Client 连接 `192.168.18.72:49100`，不要再启动第二个实例。 |
| PID 是当前账号但不是 6.0.1，或启动参数错误 | 先保存日志和 PID 信息，再按第 3 步优雅停止后重新启动。 |
| PID 属于其他用户 | 不要停止；换用其他信令端口（例如 `49101`）并同步修改 Client，或联系进程所有者。 |
| `PORT_PID` 为空 | 确认 `ss -lntp | grep ':49100'` 仍为空后，再运行 `start_isaacsim_streaming.sh`。 |

#### 3. 只停止确认过的旧实例

只有在第 1 步确认 PID 属于当前账号、并且确实是需要替换的 Isaac 实例时，才执行下面命令。不要使用 `pkill -f kit` 或 `kill -9`，它们可能误伤别人的 Isaac、训练或采集进程。

```bash
test -n "$PORT_PID"
test "$(ps -o user= -p "$PORT_PID" | tr -d ' ')" = "$(id -un)"

kill -TERM "$PORT_PID"
for _ in $(seq 1 15); do
  kill -0 "$PORT_PID" 2>/dev/null || break
  sleep 1
done

ss -lntp | grep ':49100' || echo '49100 已释放'
pgrep -af "$HOME/isaacsim-6.0.1" || true
```

如果 15 秒后端口仍被同一实例占用，先查看该实例的 streaming 日志和父进程；不要扩大到全局进程清理。确认 `49100` 已释放后，再启动唯一一个实例：

```bash
cd ~/openarm_ws
ISAAC_ROOT="$HOME/isaacsim-6.0.1" \
ISAAC_PUBLIC_IP=192.168.18.72 \
bash alignment/start_isaacsim_streaming.sh
```

#### 4. 当前情况记录

```text
检查主机: ______________________________
检查时间: ______________________________
49100 PID: ______________________________
PID 所属用户: __________________________
是否为 Isaac Sim 6.0.1: [ ] 是  [ ] 否  [ ] 无法确认
处理方式: [ ] 复用  [ ] 优雅停止后重启  [ ] 改用其他端口  [ ] 未处理
日志路径: ______________________________
```

### A-157：新主机服务端、旧主机 GUI 的双终端启动方式

当前网络拓扑：

```text
新主机 192.168.18.72   Isaac Sim 6.0.1 + WebRTC Streaming 服务端
旧主机 192.168.18.154  Isaac Sim WebRTC Streaming Client 图形界面
```

机器人和摇杆仍连接旧主机时，不需要把硬件移动到新主机。本步骤只显示新主机的 Isaac 仿真画面。

#### 终端 1：新主机 `192.168.18.72`

```bash
cd ~/openarm_ws
ISAAC_ROOT="$HOME/isaacsim-6.0.1"
test -x "$ISAAC_ROOT/isaac-sim.streaming.sh" || { echo "找不到 Isaac Sim 6.0.1"; exit 1; }

PORT_PID=$(ss -lntpH | awk '$4 ~ /:49100$/ {
  match($0,/pid=[0-9]+/)
  if (RSTART) { print substr($0,RSTART+4,RLENGTH-4); exit }
}')

if [ -n "$PORT_PID" ]; then
  echo "49100 已被 PID=$PORT_PID 占用，先核对："
  ps -o user,pid,ppid,pgid,etime,stat,cmd -p "$PORT_PID"
  printf 'cmdline='
  tr '\0' ' ' < "/proc/$PORT_PID/cmdline" 2>/dev/null || true
  echo
  echo "确认是 Isaac Sim 6.0.1 后直接复用，不要再次启动。"
else
  mkdir -p "$HOME/isaacsim-streaming-logs"
  nohup env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
    -u AMENT_PREFIX_PATH -u COLCON_PREFIX_PATH \
    -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
    "$ISAAC_ROOT/isaac-sim.streaming.sh" \
    --no-ros-env \
    --/isaac/startup/ros_bridge_extension= \
    --/exts/omni.kit.livestream.app/primaryStream/publicIp=192.168.18.72 \
    --/exts/omni.kit.livestream.app/primaryStream/signalPort=49100 \
    --/exts/omni.kit.livestream.app/primaryStream/streamPort=47998 \
    --/rtx/ecoMode/enabled=True \
    > "$HOME/isaacsim-streaming-logs/streaming_$(date +%Y%m%d_%H%M%S).log" 2>&1 &
  echo "Isaac Sim launcher PID=$!"
fi

sleep 5
ss -lntp | grep ':49100' || true
```

服务端日志：

```bash
tail -f "$HOME/isaacsim-streaming-logs/"*.log
```

看到 `49100` 已监听或 `Isaac Sim Full Streaming App is loaded` 后，再启动旧主机 GUI。`47998/udp` 可能在客户端连接后才出现。

#### 终端 2：旧主机 `192.168.18.154` 图形桌面

```bash
rm -f /tmp/isaac_webrtc_client.log
isaacsim-webrtc-streaming-client 2>&1 | tee /tmp/isaac_webrtc_client.log
```

若命令找不到，执行：

```bash
/opt/Isaac\ Sim\ WebRTC\ Streaming\ Client/isaacsim-webrtc-streaming-client \
  2>&1 | tee /tmp/isaac_webrtc_client.log
```

GUI 填写：

```text
Server:       192.168.18.72
Signal port:  49100
Stream port:  47998
Resolution:   1280 x 720
```

点击 `Connect`。成功时旧主机窗口显示新主机的 Isaac Sim 画面。

检查命令：

```bash
# 新主机
ss -lntp | grep ':49100' || true
ss -lunp | grep ':47998' || true

# 旧主机
nc -vz -w 3 192.168.18.72 49100
tail -n 40 /tmp/isaac_webrtc_client.log
```

不要在旧主机 GUI 终端执行 `kill`，也不要使用 `pkill -f kit`。只有确认新主机的 PID 是当前账号的错误旧实例后，才按 A-156 的优雅停止流程处理。

#### 本次启动记录

```text
新主机服务端启动时间: __________________
服务端 PID: ____________________________
服务端日志: ____________________________
旧主机 Client 启动时间: _________________
Client 日志: /tmp/isaac_webrtc_client.log
Connect 结果: [ ] 成功有画面  [ ] 成功黑屏  [ ] 失败
备注: __________________________________
```

### A-161：Isaac Sim 原生双臂协同与控制参数测量

2026-09-14：当前仿真源确定为 Isaac Sim。以下测量只使用 Isaac Sim 当前打开的 OpenArm USD 和 Isaac-native 轨迹；不读取、不回放、不转换历史 MuJoCo action/observation/图像。

#### 第 1 步：只读核对 Isaac Sim stage

先在 Isaac Sim 中打开已经成功导入的 OpenArm USD，不启动真机控制。将脚本复制到新主机工作区：

```bash
cd ~/openarm_ws
python3 -m py_compile alignment/isaacsim_inspect_stage.py
```

在 Isaac Sim 的 **Window → Script Editor** 打开并运行：

```text
/home/tangyuan/openarm_ws/alignment/isaacsim_inspect_stage.py
```

这里的路径不是 Python 代码：在 Script Editor 菜单选择 **File → Open**，再选择该 `.py` 文件，然后点击工具栏的运行按钮。不要把 `/home/.../isaacsim_inspect_stage.py` 或 `cd /home/...` 粘贴到编辑区，否则会出现 `SyntaxError: invalid syntax`。

脚本只读取当前 stage，会在 Isaac Sim 输出窗口和以下文件打印结果：

```text
/tmp/openarm_isaac_stage_inspection.txt
```

先把下面字段填好，未确认前不开始动作测量：

```text
Isaac USD 路径: __________________________
Articulation root prim: __________________
左臂 articulation/prim: _________________
右臂 articulation/prim: _________________
左末端 prim: ____________________________
右末端 prim: ____________________________
左夹爪 prim/关节: ______________________
右夹爪 prim/关节: ______________________
关节顺序是否为 J1..J7 + finger: [ ] 是 [ ] 否
检查输出: /tmp/openarm_isaac_stage_inspection.txt
```

#### 第 2 步：Isaac Sim 静止噪声基线

在 Isaac Sim 内保持机器人处于安全 home 姿态，不发送变化的 action，运行 30 秒并保存每个 tick 的仿真时间、左右关节位置、末端 TF 和夹爪位置。记录：

```text
sim_control_frequency_hz: ______________
sim_tick_period_ms_p50/p95: ____________
left_joint_noise_std_rad: ______________
right_joint_noise_std_rad: _____________
left_ee_noise_std_m: ___________________
right_ee_noise_std_m: __________________
left_gripper_noise_std_rad: ____________
right_gripper_noise_std_rad: ___________
输出文件: ______________________________
```

这一步只测 Isaac Sim 自身数值稳定性，不能填写真机噪声。

#### 第 3 步：控制参数测量

对左臂、右臂分别执行相同的无接触阶跃：`home → 目标角度 → 保持 5 s → home`。目标角度、控制频率和动作保持方式写入 session metadata。每个 tick 同时保存 `command_time`、`feedback_time`、命令 qpos、反馈 qpos、末端 TF 和夹爪 qpos。

需要计算：

```text
control_frequency = 1 / median(diff(sim_time))
tracking_error_j(t) = feedback_q_j(t) - command_q_j(t)
settling_time       = first time abs(tracking_error) <= threshold and stays there
steady_rmse_j       = RMSE(last 2 s of tracking_error_j)
command_delay       = feedback_time - command_time
observation_delay   = observation_time - state_time
```

记录表：

| arm | trial_id | target | control Hz | hold mode | settling time | command delay p50/p95 | obs delay p50/p95 | joint RMSE | ee error | gripper error | 输出文件 |
|---|---|---:|---:|---|---:|---:|---:|---|---|---|---|
| left | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |
| right | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |

仿真中若没有人为注入网络/观测延迟，`command_delay` 和 `observation_delay` 只能记录为仿真调度延迟，不能当作真机延迟。

#### 第 4 步：双臂协同测量

在同一 Isaac Sim tick 中让左右臂执行一条 10--20 秒的无接触协同轨迹。使用虚拟 handoff marker 或目标位姿记录交接窗口；不需要 MuJoCo 轨迹。每个 tick 保存：

```text
sim_time
left/right action timestamp
left/right joint state
left/right end-effector position and orientation
handoff marker pose
```

计算：

```text
sync_error(t)    = t_left_action(t) - t_right_action(t)
arm_distance(t)  = ||p_left_ee(t) - p_right_ee(t)||
relative_speed(t)= ||v_left_ee(t) - v_right_ee(t)||
relative_pose(t) = T_left_ee(t)^-1 * T_right_ee(t)
handoff_window   = marker distance/orientation within threshold 的连续时间段
```

记录表：

| episode_id | 左臂角色 | 右臂角色 | handoff 目标位姿 | 同步 p50/p95 ms | 最小间距 m | 相对速度范围 m/s | 交接窗口 ms | 输出文件 |
|---|---|---|---|---:|---:|---|---:|---|
| `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |

#### 第 5 步：Isaac Sim 数据交付目录

```text
alignment/results/isaacsim_migration/<session_id>/
  metadata.yaml
  control/static_noise.csv
  control/step_left.csv
  control/step_right.csv
  bimanual/sync_motion.csv
  bimanual/metrics.json
  replay/replay_metrics.json
```

当前阶段只要完成 Isaac Sim 内部参数测量，就可以得到 `source=sim` 的记录；要宣称 sim2real 对齐通过，还必须以后追加 `source=real` 的延迟、噪声、回差、相机和接触记录。

#### A-161.1：先测双臂协同五项（Isaac Sim 原生）

本轮只测以下五项：左右臂角色、交接位置/姿态、同步时间窗口、双臂间距、双臂相对速度。它们使用一条 10 秒、无接触、Isaac-native 双臂轨迹完成；不读取 MuJoCo parquet、图像或时间戳。

先填写本次试验的名义配置。角色和交接目标是任务定义，不是由仿真自动推断：

```yaml
session_id: "isaac_bimanual_YYYYMMDD_HHMMSS"
source: "isaac_sim"
duration_s: 10.0
physics_hz: 250
left_role: "giver"          # 或 receiver/supporter
right_role: "receiver"      # 或 giver/supporter
left_ee_prim: "填写 Isaac 左末端 prim 路径"
right_ee_prim: "填写 Isaac 右末端 prim 路径"
handoff_target_frame: "World"
handoff_position_m: [x, y, z]
handoff_orientation_xyzw: [x, y, z, w]
handoff_position_threshold_m: 0.02
handoff_orientation_threshold_rad: 0.174533
```

操作顺序：

1. 打开 OpenArm USD，按第 1 步运行 `isaacsim_inspect_stage.py`，把左右末端 prim 路径填入配置；
2. 在 `/World` 下放置一个 `handoff_target` 空物体或可视 marker，位置和姿态写入上面的配置；
3. 左右臂从 home 同时开始，运动到交接点附近，保持约 2 秒，再同时回到 home；整段约 10 秒；
4. 每一个 physics tick 记录同一个 `sim_time` 下的左右 action 时间、左右末端世界坐标和世界姿态；
5. 从首个 tick 到最后一个 tick 计算下表指标，写入 `bimanual/metrics.json`。

| 参数 | 每 tick 记录 | 计算方法 | 当前 Isaac Sim 结论 |
|---|---|---|---|
| 左右臂角色 | `left_role`、`right_role` | 直接来自本次 YAML | 名义角色 |
| 交接位置/姿态 | `handoff_target` 的世界位姿、左右末端 TF | 保存目标值和达到阈值时的实际值 | 名义交接点 |
| 同步时间窗口 | `left_action_time`、`right_action_time`、`sim_tick` | `abs(left_action_time-right_action_time)`；同时进入交接阈值的连续 tick 区间 | 同 tick 下理论为 0；仍要保存实测 tick 差 |
| 双臂间距 | `p_left_ee`、`p_right_ee` | `norm(p_left_ee-p_right_ee)`；报告最小值 | 名义最小安全距离 |
| 双臂相对速度 | `p_left_ee`、`p_right_ee`、`sim_time` | `norm(diff(p_left_ee-p_right_ee)/diff(sim_time))`；报告 p50/p95/max | 名义协同速度 |

截至 2026-09-14 的实测填写结果（只填已收到并可解释的数据）：

| 参数 | 当前测量值/状态 | source | 证据/session | 解释与限制 |
|---|---|---|---|---|
| 左右臂角色 | left=`giver`，right=`receiver` | `isaac_sim` 配置 | `isaac_bimanual_20260914_155625/bimanual/metrics.json` | 当前试验名义角色；需按真实任务语义确认 |
| 交接目标位置/姿态 | `not_configured` | — | 同上 | 没有 handoff marker/target pose，不能计算达到时间或窗口 |
| 同步时间窗口 | `not_measured` | — | 没有双臂 action 时间戳 | 静态 hold 不包含动作同步测量 |
| 双臂末端静态间距 | `0.3121815343 m`（10.0011 s 内 min=max） | `isaac_sim` | `isaac_bimanual_20260914_155625/bimanual/metrics.json` | 当前姿态下的名义静态间距；不是动态最小安全距离 |
| 双臂静态相对速度 | `not_measured` | — | recorder 输出 `null` | Stage simulation clock 未推进；不能把 null 写成零 |
| 动态最小间距 | `not_measured` | — | 尚无有效 command-feedback 动态轨迹 | 静态间距不能代替轨迹最小值 |
| 静态 state 吞吐 | 约 `40.0 Hz`（1190 条/约 29.76 s）；header 瞬时频率均值 `41.9969 Hz`，范围 `31.5170–53.9818 Hz` | `isaac_sim` | `isaacsim_hold_stable_20260914_151311/control/idle_metrics/metrics.json` | 发布/录包频率，不是 articulation physics/control frequency |
| hold 下关节位置标准差最大值 | `0.0 rad`（18 DOF） | `isaac_sim` | 同上 | `simulator_position_target_each_update` 的确定性硬保持结果，不代表自然动力学噪声或真机噪声 |
| hold 下关节速度标准差最大值 | `0.0 rad/s`（18 DOF） | `isaac_sim` | 同上 | 所有速度样本均为零；属于硬保持条件 |
| command publisher 发送 | 1 条，left/right J1 目标各相对稳定 pose 改变 `0.02 rad`；命令已被 MCAP 记录 | Docker ROS | `isaacsim_dynamic_ok_20260914_162347/control/dynamic_test` | 只证明 publisher 发出且 recorder 收到 |
| command subscriber discovery | 1 个 bridge subscription endpoint，QoS reliable/volatile | ROS graph | Docker `ros2 topic info -v /sim/openarm/timestamped_joint_command` | 证明 endpoint 被发现，不证明 callback 已执行 |
| command receipt / state feedback | 最近该动态 bag 均为 `0` 条 | `isaac_sim` ROS bag | `isaacsim_dynamic_ok_20260914_162347` | command 未获得 Isaac receipt/state 证据；延迟、跟踪误差、左右同步均不计算 |
| 交接窗口 | `not_configured` | — | 未定义 marker 和姿态容差 | 需先定义 target，再做动态轨迹 |
| 相机内外参、曝光、图像时序 | `not_measured` | — | 尚无本轮 Isaac 相机记录 | MuJoCo 图像不作为本轮 Isaac 证据 |
| effort/接触 | `not_available` | `isaac_sim` | `/sim/openarm/joint_states` 的 `effort=[]` | 不能据此估力、扭矩或接触阈值 |

动态命令测量总状态：**未完成验收**。最新 Docker 查询确认 command subscription endpoint 已发现，但动态 MCAP 仅有 command 1 条，receipt/state 为 0；需先恢复有效的 Isaac update callback 和持续 state 消息，再重新录制。此前两份无效数据分别保留为 `dynamic_state_only_invalid_for_latency` 与 `command_only_unacknowledged`，不得混合计算。

`handoff_window` 的判定条件：左右末端都满足到目标点距离不大于 `handoff_position_threshold_m`，且姿态误差不大于 `handoff_orientation_threshold_rad`。连续满足条件的第一和最后一个 tick 组成交接时间窗口。

本轮输出必须包含：

```text
alignment/results/isaacsim_migration/<session_id>/
  metadata.yaml
  bimanual/config.yaml
  bimanual/sync_motion.csv
  bimanual/metrics.json
```

填写结果：

| session_id | 左角色 | 右角色 | 交接目标位姿 | 同步 p50/p95 ms | 最小间距 m | 相对速度 p50/p95/max m/s | 交接窗口 ms | 文件 |
|---|---|---|---|---:|---:|---|---:|---|
| `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` | `________` |

### A-160：Isaac Sim 作为唯一当前仿真数据源

2026-09-14：用户确认当前仿真环境已经切换为 Isaac Sim，因此上一轮 MuJoCo 采集数据不能用于当前的 Isaac Sim replay、视觉配对、双臂同步或 sim2real gap 验收。MuJoCo 文件全部保留在原路径，状态改为 `historical_only`，不删除、不覆盖。

#### 当前有效数据边界

| 数据 | 当前用途 | 是否可作为 Isaac Sim 验收输入 |
|---|---|---|
| `alignment/results/*summary.csv` 的真机 gap 统计 | 保留为真机物理参考和历史校准记录 | 可以作为真机参考；不能替代 Isaac Sim 生成的仿真轨迹 |
| `mujoco_arm_offsets.json` | 保留 offset 来源和版本审计 | 只能在明确复核后作为比较层候选，不得直接当成 Isaac 轨迹数据 |
| MuJoCo `action/`、`obs/` parquet | 历史数据结构审计 | 不可以 |
| MuJoCo 相机 JPEG | 历史数据流审计 | 不可以作为 Isaac Sim 视觉配对帧 |
| MuJoCo XML/网格/USD 资产 | 几何和模型来源 | 可以作为资产来源，但导入后必须在 Isaac Sim 内重新生成状态和动作数据 |

#### 当前必须重新生成的 Isaac Sim 数据

在 Isaac Sim 中建立新 session，不读取 MuJoCo episode 作为输入，至少生成：

```text
alignment/results/isaacsim_migration/<session_id>/
  metadata.yaml
  trajectories/isaac_native_single_arm.parquet
  trajectories/isaac_native_bimanual.parquet
  control/sim_joint_states.parquet
  bimanual/sim_tf.parquet
  vision/isaac_camera_timestamps.csv
  replay/replay_metrics.json
```

Isaac-native 采集步骤：

1. 打开已经导入并验证的 OpenArm USD；核对左右 14 个关节、夹爪关节、单位、限位和初始姿态；
2. 在 Isaac Sim 内生成固定目标的单臂轨迹，记录 action、joint state、TF 和仿真时间戳；
3. 生成左右同时动作的双臂轨迹，记录统一 tick、相对位姿、双臂距离和相对速度；
4. 启用五路 Isaac 相机，记录图像、CameraInfo 和同一仿真时间戳；
5. 在上述 Isaac-native 数据上做 replay，输出 `replay_metrics.json`；
6. 只有 Isaac-native replay 通过后，才与真机重新采集的数据做 sim2real 比较。

#### 本阶段验收状态

```text
当前仿真源: Isaac Sim
MuJoCo action/obs 是否禁用: [x]
MuJoCo 图像是否禁用: [x]
MuJoCo 模型资产是否保留为几何来源: [x]
Isaac-native 单臂 episode: [ ]
Isaac-native 双臂 episode: [ ]
Isaac-native 五路视觉记录: [ ]
Isaac replay metrics: [ ]
sim2real 对齐验收: [ ]
```

### A-158：任务一——视觉、双臂协同、控制信息记录完成版

视觉、双臂协同和控制的后续测量统一更新到 [`isaacsim_measurement_log.md`](isaacsim_measurement_log.md)；本节保留已有证据与历史审计记录。

2026-09-14：本节记录任务一“视觉、双臂协同、控制信息”的当前采集进度；内部 `intern_data_engine` 的可复用性评估留到任务二。Isaac Sim 表项依据本轮 terminal/MCAP/metrics 输出；不能把失败录制、endpoint discovery 或计划中的采集误记为测量通过。

#### 1. 已采集证据

| 类别 | 已有证据 | 当前结论 |
|---|---|---|
| 历史关节位置和固定偏差 | `alignment/results/*summary.csv`（历史 43 个 summary）、`alignment/mujoco_arm_offsets.json`、`alignment/mujoco_calibration.yaml` | 历史静态/方向/动态校准资料保留审计；来源及模型为旧流程，不能当成本轮 Isaac-native 测量或直接作为真机当前状态。 |
| MuJoCo 动作 | `.../20260909-160842-b6b2d210/dataset/episodes/0/action/arms/{left,right}/state.parquet` | 历史数据，保留用于审计；不作为 Isaac Sim action 输入。 |
| MuJoCo 观测 | 同一 episode 的 `obs/arms/{left,right}/state.parquet` | 历史数据，保留用于审计；不作为 Isaac Sim observation 输入。 |
| Isaac Sim 关节状态与映射 | `isaacsim_hold_stable_20260914_151311/control/idle_30s`、`control/idle_metrics/metrics.json`（新主机 session） | 已从 `/sim/openarm/joint_states` 收到 18 DOF 的 name/position/velocity；关节顺序为左右 J1--J7 交替，随后左右各两个 finger。当前 state 吞吐约 40 Hz；不是 physics/control rate。`effort=[]`。 |
| Isaac Sim 静止控制基线 | 同一 hold session；`action_hold_mode=simulator_position_target_each_update` | 1190 条/约 29.76 s；18 DOF position/velocity std 均为 0。仅是确定性硬 position-hold 基线，不代表自然动力学、真机噪声或实际控制频率。前两段无 hold/收敛数据保留为无效静止噪声试次。 |
| Isaac Sim 双臂静态几何 | `isaac_bimanual_20260914_155625/bimanual/metrics.json`（新主机 session） | left=`giver`、right=`receiver` 为名义角色；当前姿态下末端间距 `0.3121815343 m`（10.0011 s，min=max）。不是动态最小安全距离。 |
| Isaac Sim 双臂动态/action | `isaacsim_dynamic_20260914_161627`、`isaacsim_dynamic_ok_20260914_161929`、`isaacsim_dynamic_ok_20260914_162347`（新主机 session） | 161627 只录到 state；161929 是 0-message 空包；162347 只录到 1 条 command，receipt/state 为 0。只能确认 ROS command subscriber endpoint 已发现；command 应用、反馈延迟、双臂同步、动态间距/相对速度均未验收。 |
| Isaac Sim 相机参数枚举 | `isaac_camera_20260915_091927/vision/camera_params.json`（新主机 session） | 枚举到的 4 个 `Camera` prim 均是编辑器视口：`/OmniverseKit_Persp`、`/OmniverseKit_Front`、`/OmniverseKit_Top`、`/OmniverseKit_Right`；不是 ceiling/head/wrist 任务相机，不能计入视觉采集或标定。任务相机、分辨率、FPS、图像、CameraInfo、畸变、曝光、光照、遮挡和帧时间戳均未配置。 |
| 历史 MuJoCo 视觉 | `cameras/{ceiling,head_left,head_right,wrist_left,wrist_right}` | 仅作为历史审计；不作为本轮 Isaac Sim 视觉证据。 |
| 关节映射/限位 | `ker_mapping.yaml`、`alignment/mechanical_limits.csv`、`alignment/openarm_v20_reference.urdf` | 关节名、左右方向、源索引和限位已有文件证据。 |
| Isaac Sim 工作区/物体盘点 | `isaac_workspace_20260915_092529/workspace/stage_inventory.json`（新主机 session） | `geometry_item_count=0`。当前 stage 仅打开 OpenArm 本体及其 USD 组织层，没有任务物体、桌面、夹具、容器或障碍物可作为工作区测量对象。 |
| MuJoCo→Isaac 资产 | `alignment/isaacsim_assets/mujoco_v2/` | 厂家 v2 XML、网格和场景已形成只读快照；已成功打开的 USD 另行记录。 |

现有 episode 的 `success: false`，任务说明是“映射关节和仿真相机验证”，不能作为完整双臂任务成功样本。

#### 2. 尚未采集、必须补齐的内容

本轮采集范围限定为**双臂协同、视觉和控制**。物体/工作区和接触留待有真实任务物体、桌面或传感器后单独开展；不以空场景或默认物理参数补填。

| 类别 | 缺少的记录 | 最小可验收文件 |
|---|---|---|
| 视觉 | Isaac Sim 相机图像/CameraInfo/外参/帧时间戳；真机内外参、畸变、曝光、光照和遮挡 | `vision/camera_info_<id>.yaml`、`vision/*.bag`、`vision/frame_timestamps.csv` |
| 双臂协同 | 交接目标/姿态和窗口；带共同时间基准的左右 action；有效动态相对速度、动态最小间距；command receipt/state 闭环 | `bimanual/*.bag` 或 parquet、`bimanual/config.yaml`、`bimanual/metrics.json` |
| 控制 | Isaac Sim physics/control tick 频率；有效 command→receipt/state 延迟、跟踪误差、双臂 action skew；真机 command/observation 延迟和关节噪声 | `control/dynamic_test`、`control/latency_metrics.json`；真机数据后续独立采集 |
| 物体/工作区 | `deferred`：等真实任务资产、桌面或工装确定后再测 | 本轮不采集；当前 scene inventory 为 0 |
| 接触 | `deferred`：等物体/工作区与接触传感器定义后再测 | 本轮不采集；当前没有接触对象且 `/sim/openarm/joint_states` 的 `effort=[]` |

下一组按表格进入 Isaac Sim 视觉参数。运行 [`isaacsim_capture_camera_params.py`](isaacsim_capture_camera_params.py) 可只读枚举当前 USD 中所有 `Camera` prim，保存世界位姿、焦距、光圈和裁剪范围到 `vision/camera_params.json`。若 `camera_count=0`，说明当前 OpenArm USD 没有相机，视觉项保持 `not_configured`；脚本不会创建相机、渲染图像或修改 USD。分辨率、FPS、畸变、曝光、光照、遮挡和图像时间戳仍需在相机创建并启用渲染后单独记录。

#### 3. Isaac Sim 对齐清单

按以下顺序执行，并保持真机原始反馈不变：

1. 关节名称、顺序、单位、左右正方向、限位和夹爪方向；
2. 基座坐标、关节初始位姿和 USD articulation 结构；
3. 控制周期、动作保持、执行器增益/阻尼、限幅、命令/观测延迟；
4. 固定 offset 和 J5/J6 方向 offset（只放 replay/比较层）；
5. 双臂统一时钟、同步窗口、相对位姿、相对速度和交接触发；
6. 相机内外参、分辨率、FPS、曝光、光照、背景、遮挡和噪声；
7. 物体/工作区几何、质量、惯量、摩擦、接触和滑移模型。

当前已知方向补偿仍以 `alignment/mujoco_arm_offsets.json` 为准。任何正式 USD/URDF 修改都必须在独立 replay 通过后再做。

#### 4. 轨迹 replay 验证状态和执行单

当前没有 OpenArm 的 Isaac replay adapter，也没有 `sim_joint_states.parquet`、`sim_tf.parquet` 或 `metrics.json` replay 输出。因此 replay 尚未验收；历史 MuJoCo episode 不再作为 Isaac 验证输入。

第一条 replay 使用已有 episode 0，只做离线单臂，再做双臂：

```text
Isaac Sim-native action episode（Isaac 时间戳）
  -> OpenArm 关节名/顺序/单位映射
  -> 固定与方向 offset（比较层）
  -> Isaac Sim articulation controller
  -> sim_joint_states + sim_tf + camera_frames
  -> replay_metrics.json
```

每次 replay 填写：

| replay_id | 输入 episode | Isaac USD/场景 | offset 文件 | 单/双臂 | 输出目录 | 状态 |
|---|---|---|---|---|---|---|
| `________` | `________` | `________` | `________` | `________` | `________` | `[ ] 未开始 [ ] 进行中 [ ] 通过 [ ] 失败` |

验收指标：

| 指标 | 结果 | 目标/备注 | 通过 |
|---|---:|---|---|
| action 时间戳完整率 | `________` | 100% | `[ ]` |
| qpos 维度/关节顺序 | `________` | 8 维、左右映射一致 | `[ ]` |
| Isaac 输出帧数 | `________` | 与输入时间范围对应 | `[ ]` |
| 单臂逐关节 RMSE | `________` | 对照已有静态/方向基线 | `[ ]` |
| 双臂同步 p50/p95 (ms) | `________` | 先记录分布 | `[ ]` |
| 相机帧数/FPS/时间戳抖动 | `________` | 与配置一致 | `[ ]` |
| 接触事件 | `________` | 无传感器写 `not_available` | `[ ]` |

#### 5. 执行问题与修复记录

| 时间 | 问题/无效试次 | 原因 | 修复与当前结论 |
|---|---|---|---|
| 2026-09-15 | `isaac_bimanual_dynamic_*`：901 样本、15.0139170270 s；末端间距固定为 `0.3117671302 m`，相对速度均值/最大值均为 `0.0 m/s`。 | 采集脚本通过 USD `XformCache` 读取末端变换，未读取 PhysX articulation 的动态 link 位姿。 | 改用 `RigidPrim.get_world_poses(usd=False)`。重测得到有效 PhysX 动态末端间距 `0.3019701336–0.3111607593 m`，相对速度均值 `0.0004281507 m/s`、最大 `0.0381394014 m/s`。 |
| 2026-09-15 | 三段 J1 跟踪试验中，第 1、3 段未在约 2 s 窗口达到 `0.002 rad` 容差；第一条 raw command 未进入 bag。 | 当前仅证实 command 已 receipt 并有 state 反馈；目标未收敛的具体控制器增益、限位或动作保持原因尚未隔离。录包端在首条 publisher 发送时尚未完整订阅 command topic。 | 记录各段初始/最终误差，不能将该试验称为跟踪通过。后续使用固定轨迹发布器、先等待 recorder subscription，再分别测执行器增益、限位和 position target 保持行为。 |
| 2026-09-15 | `isaacsim_control_fixed_20260915_101245` 只录到 A、B 两段：第三段 A 的 header 为 `1789438384.385306996`，晚于 bag 结束时间 `1789438381.751698999`。 | recorder 的 `16 s` timeout 从启动录包时开始计时，包含 recorder 就绪等待与轨迹启动前等待；三段轨迹本身持续约 12 s。 | 将 recorder timeout 改为 `21 s`，保证覆盖就绪等待、A→B→A 三段和末段反馈窗口。 |
| 2026-09-15 | 完整固定轨迹试验 `isaacsim_control_fixed_20260915_101449` 已录到 command/receipt/state 各 `3/3/659` 条；发布侧 command→receipt 为 `8.96–27.95 ms`，但 A 段（第 1、3 段）仍未达到 `0.002 rad` 容差。 | 固定发布器已排除 CLI 启动及订阅匹配造成的约 `0.66 s` 表观延迟；未收敛原因位于 Isaac 侧 action/position-target 的持续保持、控制增益、限位或 articulation 配置，尚未隔离。 | 后续在桥接 update callback 中验证 pending target 是否每帧持续下发，并记录 physics/control tick；在根因确认前不标记 J1 跟踪通过。 |
| 2026-09-15 | 原桥接脚本仅在收到 callback 的那个 update 调用一次 `apply_action`，随后清空 `pending`。 | 单次 action 不能证明 position target 会在后续仿真 update 中持续保持。 | 已将 `isaacsim_timestamped_command_bridge.py` 改为保存 `active_target`，并在每个 update 调用 `apply_action`；Console 会打印 `OPENARM_POSITION_TARGET_HELD`。该修复尚待固定轨迹重测验证。 |
| 2026-09-15 | `isaacsim_control_hold_20260915_103359` 的 command/receipt 均为 3 条，但 state 为 0。诊断显示 `ACTIVE_APPLY_COUNT=5909`，且 `get_joint_positions()` 可返回 `(1,18)` 数组。 | state publisher 将二维 `(1,18)` 的 position 数组逐项转换为 `float`，在 state 构造分支报错；position target 的持续下发本身正常。 | bridge 改为用 `np.asarray(...).reshape(-1)` 压平 position 和 velocity 后再填充 `JointState`。重载桥接后重测，要求 command、receipt、state 都非零。 |
| 2026-09-15 | `isaacsim_control_hold_valid_20260915_104717` 的 command/receipt 为 `3/3`，但 state 为 `1949/20.7212 s`（约 `94.1 Hz`）。 | 旧 `OPENARM_ACTUAL_STATE_ARMED` publisher 未停止，新 v2 state publisher 同时向 `/sim/openarm/joint_states` 发布，导致同一 bag 混入两个 state 流。 | 在 Isaac Script Editor 停止旧 publisher，仅保留 `OPENARM_STATE_V2_*` publisher 后重测；当前 bag 不用于跟踪、频率或延迟参数。 |
| 2026-09-15 | 停止已知旧 publisher 后，`/sim/openarm/joint_states` 仍显示 3 个 publisher，其中 2 个为匿名 endpoint。 | 匿名 Isaac/ROS publisher 无法从当前 Script Editor 会话按已知对象名可靠停止。 | state publisher 改发到隔离 topic `/sim/openarm/joint_states_v2`；后续 bag 与分析器显式使用该 topic，避免混入旧 state 流。 |
| 2026-09-15 | `isaacsim_control_hold_v2_20260915_105143` 以隔离 state topic 完成 `command/receipt/state=3/3/628` 的 21 秒固定轨迹录包。第 1、3 段 A 仍未达到 `0.002 rad`；第 2 段 B 在 `1.178459901 s` 首次同时达到容差，但结束时 left J1 误差回到 `0.0022176164 rad`。 | 桥接诊断的 `ACTIVE_APPLY_COUNT` 持续递增，且 v2 state 是单独录入；发布器启动、state 形状和旧 topic 混流均已排除。剩余未收敛来自 articulation actuator/限位/目标幅值等控制侧条件，尚未隔离。 | 该 bag 可用于闭环跟踪参数；不将三段试验标记为跟踪通过。下一步采集 physics/control tick，并检查 J1 actuator 配置、限位和对 A/B 目标的实际可达性。 |
| 2026-09-15 | 首次运行任务相机脚本时，Isaac Camera 拒绝 `30 Hz`：`frequency of the camera sensor needs to be a divisor of the rendering frequency`。未生成图像或测量文件。 | Isaac 的当前 rendering frequency 与 `30 Hz` 不整除；Camera sensor frequency 必须是其整数因子。 | 将首轮可复用相机采集改为 `1 Hz`，它是任意整数渲染频率的因子。成功采集后再从有效渲染频率选择更高的整除采样率。 |

#### 6. 任务一交付判定

```text
信息盘点表已写入 README: [x]
已采集证据路径已列出: [x]
待采集项和最小文件已列出: [x]
Isaac Sim 对齐顺序已列出: [x]
轨迹 replay 输入/输出规范已列出: [x]
Isaac 离线 replay 实际通过: [ ]
下一步负责人: __________________________
下一步日期: ____________________________
```

### A-159：参数记录的仿真/真机来源边界

2026-09-14：针对“这些参数是否可以全部通过仿真完成”的问题，结论是：仿真可以完成名义值、几何关系和算法 replay；不能替代真机对延迟、噪声、回差、驱动器响应和实际接触的测量。只有同时记录 `source=sim` 和 `source=real`，才能形成 sim2real 对齐证据。

#### 1. 双臂协同

| 参数 | Isaac Sim 可记录 | 必须真机记录 | 记录结论 |
|---|---|---|---|
| 左右臂角色 | 可以，来自 replay 配置 | 需要确认实际操作角色 | 仿真记录名义值，真机确认任务语义 |
| 交接位置/姿态 | 可以，直接读取末端 TF | 需要实测交接成功区域和人工修正 | 仿真可给目标，真机给容差 |
| 同步时间窗口 | 可以，按同一 simulation tick 计算 | 必须测真实 action 到达时间差 | 仿真只能证明调度同步，不能证明网络/控制同步 |
| 双臂间距 | 可以，读取左右末端或连杆位姿 | 需要验证真实标定误差和安全裕量 | 仿真完成名义轨迹，真机验证最小安全距离 |
| 双臂相对速度 | 可以，从仿真 TF 求导 | 需要真实控制周期和反馈速度 | 两边都记录，比较分布 |

#### 2. 控制

| 参数 | Isaac Sim 可记录 | 必须真机记录 | 记录结论 |
|---|---|---|---|
| 控制频率 | 可以，记录 physics/control tick | 必须测实际发布和执行频率 | 仿真记录设定值，真机记录实测值 |
| 动作保持方式 | 可以，明确 zero-order hold 或插值 | 需要确认真机控制器实际行为 | 两边配置必须一致 |
| command→feedback 延迟 | 只能记录仿真内设定延迟 | 必须用同一单调时钟测量 | 不能用仿真值替代真机值 |
| observation 延迟 | 可以记录人为注入的模型延迟 | 必须从真机时间戳测量 | 先实测，再在 Isaac 注入同分布延迟 |
| 关节噪声 | 可以注入指定噪声并记录 | 必须记录静止段真实噪声 std | 仿真噪声参数由真机统计确定 |
| 关节回差/方向误差 | 可以实现迟滞模型 | 必须由正/负方向稳定段测量 | J5/J6 不能只用一个平均 offset |
| 末端位置/姿态误差 | 可以计算模型跟踪误差 | 必须由真实 TF 或外部测量验证 | 仿真值只能作为基线 |
| 夹爪误差 | 可以读取仿真关节状态 | 必须测真实夹爪反馈和闭合结果 | 本轮手指补偿仍暂不加入 |

#### 3. 可以先在 Isaac Sim 完成的记录

在不连接真机、不发送 ROS 控制命令的情况下，可以先填完：

```text
sim_joint_names/order/limits
sim_control_frequency
sim_action_hold_mode
sim_left_right_roles
sim_handoff_pose
sim_arm_distance
sim_relative_speed
sim_camera_pose/intrinsics/render_fps
sim_object_geometry/mass/inertia/material
sim_workspace_collision_geometry
sim_replay_timestamps
```

这些记录的 `source` 统一写 `isaac_sim_nominal`，不能写成 `real` 或 `sim2real_validated`。

#### 4. 必须等真机恢复后完成的记录

```text
real_command_to_feedback_latency_p50_p95
real_observation_latency_p50_p95
real_joint_noise_std
real_joint_backlash_or_direction_residual
real_end_effector_pose_error
real_gripper_error
real_left_right_sync_error
real_camera_intrinsics/extrinsics/timestamps
real_object_mass/friction/contact_force
real_workspace_pose/tolerance
```

真机记录完成后，才把统计结果作为 Isaac Sim 的延迟、噪声、迟滞、摩擦和接触参数。真机电源未恢复时，上述字段必须填写 `not_available`，不能用仿真默认值补写。

#### 5. 记录表增加来源列

后续每个参数都使用以下格式，避免把仿真结果误当作真实校准：

| 参数名 | 数值 | 单位 | source (`sim`/`real`/`both`) | 原始文件 | Isaac 配置文件 | 是否完成 sim2real 验证 |
|---|---:|---|---|---|---|---|
| `________________` | `________` | `________` | `________` | `________` | `________` | `[ ]` |
| `________________` | `________` | `________` | `________` | `________` | `________` | `[ ]` |

判定规则：

```text
只有 source=both 且仿真/真机使用同一时间基准、同一关节映射和同一场景定义，
才可以标记“sim2real 对齐通过”。
```

### A-160：2026-09-15 真机双 CAN 总线节点间歇缺失，暂停 ROS 控制

**现象与结论。** 真机旧主机的 `can0/can1` 已通过 `openarm-can-cli can_configure` 配置为 CAN-FD：仲裁相位 `1 Mbit/s`、数据相位 `5 Mbit/s`，两接口均为 `UP`、`LOWER_UP`、`ERROR-ACTIVE`，且 TX/RX error counter 为 `0`。因此 PCAN-USB FD 适配器和 Linux SocketCAN 配置正常。`openarm-can-cli discover` 在多次扫描中均能发现部分电机并读取其 `5 Mbps (FD)` 内部设置，但每次能发现的 ID 集合变化：

| 总线 | 已出现过的回复 ID | 最近一次证据 | 当前判定 |
|---|---|---|---|
| `can0`（真机配置中为右臂） | `0x03`、`0x04`、`0x05`--`0x08`；CAN 插头交换后的 A/B 测试为 0 个 | 绿灯状态下最新仅 `0x04`、`0x06`、`0x07`、`0x08`；缺 `0x01`、`0x02`、`0x03`、`0x05` | 节点不完整、间歇回复；A/B 结果不可单独归因 |
| `can1`（真机配置中为左臂） | `0x04`--`0x08`，其后出现过 `0x04`、`0x07`、`0x08`、`0x07`/`0x08`；随后为 0 个 | 绿灯状态下最新仅 `0x04`、`0x07`、`0x08`；缺 `0x01`--`0x03`、`0x05`、`0x06` | 节点不完整且明显不稳定 |

硬件插件 [`openarm_simple_hardware.cpp`](../src/openarm_ros2/openarm_hardware/src/openarm_simple_hardware.cpp) 对每条手臂固定初始化 ID `0x01`--`0x07` 和夹爪 ID `0x08`；双臂真机 bringup 需要每条总线完整、稳定地回复 `0x01`--`0x08`。不能将当前不完整扫描当作完整真机反馈。

**已排除的因素。** 当前 ROS 图中四个 `forward_position_controller/commands` topic 的 publisher count 均为 `0`，每个只有相应控制器的一个 subscription；系统中只有一个 `ros2 launch openarm_bringup ...` 和一个 `ros2_control_node`。因此本轮节点缺失不是由 KER、Isaac bridge 或第二个 ROS 指令发布者造成。

**monitor 试验的边界。** `openarm-can-cli monitor` 不是只读工具：输出会显示 `Enabling motors...`，结束时显示 `All motors DISARMED safely.`。在本轮中，它对当时可发现的 `can1` ID `0x04`--`0x08` 与 `can0` ID `0x03`、`0x05`--`0x08` 返回了真实位置、速度、扭矩与约 `28`--`31°C` 的温度，说明这些节点在该瞬间有供电和 CAN 响应；工具退出后已禁扭矩。后续排查不得把 `monitor` 当作无运动诊断，也不得用它作为整臂使能手段。

**安全状态。** 当前禁止启动 `openarm.bimanual.launch.py`、禁止运行 Isaac--真机统一路由器、禁止发送 ROS 位置指令。现有硬件插件的 `on_activate()` 会无条件 `enable_all()` 和 `return_to_zero()`，当部分电机无反馈时存在振荡和非预期运动风险。不要执行 `change_id`、`change_baud`、`set_zero`、`clear_error` 或批量 `enable`。

**逐项排查顺序。** 每项完成后只运行对应总线的 `discover`；只有两条总线各自连续三次稳定发现 `0x01`--`0x08`，才进入 ROS 真机测试。

1. 停止全部真机 ROS bringup 与遥操作节点，保持电机禁扭矩；保留 `can0/can1` 为 `UP` 的 `1M/5M FD` 配置。
2. 按缺失 ID 对应的物理电机逐个检查驱动供电、状态灯、供电接头与 CAN 输入/输出接头。由于 ID 集合跨次变化，优先检查电源/CAN 串接、线束弯折处和中继接头，而非修改软件参数。
3. 检查每条 CAN 总线两端终端电阻、CANH/CANL 极性和主线/支线连接；一个上游串接节点或接头松动可导致后续多个 ID 间歇消失。
4. 每做一处物理调整后运行 `sudo openarm-can-cli -i canX discover`，记录完整输出；不要只凭电机灯色判断通信已恢复。
5. 完整发现后再复查三次扫描稳定性；随后才启动唯一真机 bringup，验证 `/joint_states` 为真实、非全零且可重复的反馈，最后才进行低幅值单关节和 Isaac 对比测试。

**A/B 测试补充。** 交换两只 PCAN 适配器上的 CAN 插头后，`can0` 与 `can1` 均报告 `No motors detected`。该结果未显示故障固定在某一个 PCAN 通道，也未显示故障随某一根线单独移动；它可能由共同供电/急停状态或交换后插头未完全插紧造成。下一步必须断电并恢复原始插头对应关系，复查两条插头锁扣与主电源/急停，再进行原接线下的单总线扫描；在原接线复现稳定基线前，不再以本次 A/B 结果判断适配器故障。

**反馈不稳定的机理与根因排序。** `discover` 会对 ID `0x01`--`0x10` 发送查询，并只把收到有效回复的节点列入结果。当前同一节点有时出现、有时消失，表示 PCAN 在不同扫描中不能稳定收到该节点的 CAN 回复；它不是 ROS topic、Isaac Sim 或关节控制参数造成的。`can0/can1` 均为 `ERROR-ACTIVE` 且误码计数为零，只能证明 PCAN 和 Linux 接口未进入 bus-off，不能证明每个电机节点均可达。`enable` 的成功文本与不完整 `discover` 同时出现，因此该文本只能证明工具已向目标 ID 发送使能帧，不能替代逐电机回复证据。

| 优先级 | 候选根因 | 与当前证据的关系 | 区分方法 |
|---|---|---|---|
| 1 | 电机供电、急停继电器、保险或供电接头间歇 | 节点集合跨次变化；部分节点能回传温度和位置，而另一些无回复 | 断电后检查每个驱动供电插头、保险与电源输出；上电后复扫 |
| 2 | CAN 串接/中继接头、线束弯折或 CANH/CANL 接触不良 | 同一总线只出现部分节点且集合变化；一个上游故障可使后续多节点消失 | 断电后逐段复插 CAN 输入/输出接头；每处理一段后连续扫描三次 |
| 3 | 终端电阻或总线拓扑异常 | 会造成反射和随机丢帧，即使接口保持 `ERROR-ACTIVE` | 断电后在每条总线 CANH--CANL 间测等效电阻；典型双端 120 Ω 终端应约为 60 Ω，具体以设备接线设计为准 |
| 4 | 单个驱动板故障或电机内部 ID/协议不一致 | 某个固定 ID 永久无回复时成立 | 在供电与总线完整后，对固定缺失 ID 单独复扫；禁止直接改 ID 或波特率 |
| 5 | PCAN 通道或 Linux CAN 配置 | 可能性较低：两通道此前均发现过电机，且配置、速率和接口状态正常 | 恢复原接线后复扫；若故障稳定固定在同一 PCAN 通道，再更换通道/适配器验证 |

**现场排查顺序。** 先执行双总线禁扭矩，关闭真机 bringup、KER、Isaac 路由器；然后断主电源再触碰 CAN 或供电插头。恢复原始 `can0=右臂`、`can1=左臂` 接线后，优先检查共同电源/急停，再按每条手臂从主线到各电机的顺序逐段复插。每次上电后只运行三次 `discover`；记录每次 ID 集合。不要在缺失节点存在时启动 `openarm.bimanual.launch.py` 或发送 ROS 位置命令。

**A-160 更正（2026-09-15，优先级高于本节前述 `discover` 推断）。** 复查 `openarm-can-cli discover` 源码后确认：该子命令会依次把 SocketCAN 重配为多种仲裁/数据速率；对每个 ID 临时按 `DM4310` 初始化；切换为 `PARAM` callback；仅查询 `MST_ID` 参数两次，每次只等待约 30 ms。它不是现有真机硬件插件的状态读取路径。真机插件使用各关节真实电机类型和持续的 `STATE` callback；扫描中出现的 `INVALID PARAM DATA` 表明状态帧被参数解析器拒绝。因此 `discover` 返回的部分 ID 或零 ID 是此扫描方法的假阴性，不能用于断言真实电机缺失、供电失败或 CAN 链路不稳定。

本轮更强的有效证据是：电机已全部变绿、真机可回零，且右 J7 已通过 `/right_forward_position_controller/commands` 接收 `+0.02 rad` 并正常运动与回零。这推翻了本节前述“必须通过连续完整 discover 才可启动 ROS”的结论。后续真机验收以唯一 bringup 正常运行、`/joint_states` 完整且合理、低幅值命令和真实反馈一致为准。`discover` 仅保留为离线协议/参数调试工具，不得在运行中的真机控制或 Isaac--真机对齐试验中反复运行。

### A-161：2026-09-15 全轴固定点 baseline 在 Isaac 未跟踪时自动中止

获授权的 `openarm_real_sim_bimanual_fixed_0p1_baseline_v1` 使用每轴绝对 `0.1 rad`、其余轴保持起点、`50 Hz` 保持 `3 s`、返回起点 `1 s` 的协议。试验实际完成左 J1--J4 四轴，真机终值分别为 `0.08335`、`0.08526`、`0.08946`、`0.09060 rad`，均随后回程。同期 Isaac 终值分别为 `−0.00890`、`0.00250`、`0.27304`、约 `0 rad`，没有跟踪共同的 `0.1 rad` 目标。因此这些数据只能证明真机流式执行链已工作，不能用于计算 Sim2Real gap；未继续驱动剩余十轴。

试验被中断后，router 已退出，左右真实 command topic 均复查为 `Publisher count: 0`。原始文件位于 `alignment/results/openarm_real_sim_bimanual_fixed_0p1_baseline_v1/`。执行器现将 Isaac 目标误差 `>0.01 rad` 作为自动中止门：该轴仍先回程和写入 JSON，随后阻止后续任何真实关节命令。后续必须先修复并 sim-only 验证 Isaac 全轴 position drive；继续余下轴需要新的逐次授权。

### A-162 — `openarm_real_sim_bimanual_offset_identification_v1` 启动阶段中止（2026-09-15）

已授权的 14 轴辨识在左 J1 启动阶段中止，没有生成任何 per-joint JSON，因此不能作为测量或校正证据。检查发现后台 `dual_target_command_router.py` 未随 runner 异常退出而结束；已立即终止，随后两个真实 forward controller command topic 的 publisher count 均为 `0`。在重新授权前，新增 recorder `--preflight-only` 无动作检查，并加强 runner 对 router PID 的 TERM/wait cleanup。不得从本次中止试次估计 offset、scale、backlash 或 delay。

### A-163 — `openarm_real_sim_bimanual_offset_identification_v1` 部分完成后安全停止（2026-09-15）

真机已通过持久化 `tmux` bringup 重新使能并受控回零；启动环境显式使用 `ROS_DOMAIN_ID=42`、`rmw_fastrtps_cpp`，双端 health 随后为 READY。左 J1 完成了完整三重复 `+0.05→0→-0.05→0→+0.10→0` 序列，原始记录为 `results/openarm_real_sim_bimanual_offset_identification_v1/openarm_left_joint1.json`，52/52 router receipts accepted。左 J2 启动后，监控端已停止 router；该轴没有完整的双端路由记录，已删除其 JSON 并停止整个 session。停止后左右真实 controller command topic 的 publisher count 均为 0。不得将左 J1 单轴结果推广到其余 13 轴；继续采集需要新的逐次授权。

### A-164 — remaining-13 identification stopped by router safety gates (2026-09-15)

After valid preflight and single-router startup, left J2 and left J3 completed their three-repeat identification sequences. During left J4, the router stopped the real stream on stale feedback, then rejected return-substep targets as `target_out_of_limits:openarm_left_joint4`. The runner exited; it did not proceed to left J5--J7 or either right-arm joint. The router is no longer running. Files for left J1--J3 are complete; left J4 is partial/invalid for fitting and must not be used. Resolve state freshness and compare the planned J4 return against `mechanical_limits.csv` before any future physical attempt.
