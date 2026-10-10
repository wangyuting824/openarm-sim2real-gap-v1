# 第三人称 RealSense 与真实硬件 gap

## 先区分两类相机标定

- RealSense factory RGB、Depth 及 RGB↔Depth 变换，只能作为当前序列号、固件、分辨率和 FPS 下的设备内参记录；它不是机器人外参。
- 第三人称外参是固定的 `T_base_camera`。必须以机器人基座和物理世界中的同一参考板建立，不能从 factory CameraInfo 推断。

先确认 USB 连续出帧、图像时间戳持续变化、当前 RGB/depth profile 已记录。UVC/USB 不稳定时，停止标定，不用掉帧数据拟合外参。

## 无夹爪贴码的首选方案

1. 把 AprilTag/GridBoard 刚性固定在工作台，记录其尺寸、ID 排列和板坐标。
2. RealSense RGB 检测板并以 PnP 求 `T_camera_board`。
3. 使用**已物理验收**的 TCP 触碰板上至少四个非共线已知点，拟合 `T_base_board`。触碰轨迹必须另有命名授权、低速、单一命令源和回退条件。
4. 合成 `T_base_camera = T_base_board · inverse(T_camera_board)`。
5. 用未参与拟合的 6–10 个板观测验证基座中的板位姿一致性；只在通过后发布 `base → realsense_color_optical_frame` 静态 TF。

`T_camera_board` 与 `T_base_board` 的方向必须在结果中显式记录。深度 optical frame 应由 RealSense factory RGB-depth 关系派生，不复制 RGB 外参。

## 双臂冗余与替代方式

- 左右臂可分别触碰同一板点，比较两个 TCP/base 链的残差；这是外参验收，不是把两臂数据无条件合并。
- 可以把小型 Tag 刚性装在腕部/工具座，用于重复检查或自动采样；不要贴在会开合或形变的手指上。若未测量 `T_tool_tag`，它只能检查相对漂移，不能替代绝对外参。
- 点云/CAD 配准只能作为冗余检查。深度遮挡、反光及局部最优使其不适合作为唯一几何基准。

## 真机 gap 的测量顺序

完成第三人称外参后，依次测量：

1. 命令—反馈时延、上升时间、稳态误差、反向死区、速度与加速度饱和；每轴独立、其余轴保持、每个方向重复。
2. 在多种重力姿态和正反速度下记录 position、velocity、effort/current 和温度；先分离重力项，再拟合每轴摩擦、阻尼、回差和有效载荷。
3. 标定夹爪目标开度到指尖距离、闭合接触点和可靠接触阈值。

不要把一个关节的摩擦或延迟分布套用到其他轴。每个候选参数均需保留原始日志、姿态/载荷域和独立留出验证；未验收参数不进入活跃控制器或 TF。
