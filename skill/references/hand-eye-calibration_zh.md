# 手部相机手眼标定规则

本规则用于安装在 OpenArm 腕部/末端的 eye-in-hand 相机。它只负责从已记录的机器人姿态和标定板观测求出刚体变换，不会启动电机、发送 ROS 命令或自动发布 TF。

## 1. 坐标与数据

每个样本必须包含同一时刻的 `T_base_tool`（机器人 base 到工具）和 `T_camera_target`（相机到棋盘格/AprilTag 标定板），并保存图像时间戳、机器人状态时间戳、帧号和 session id。推荐 12--30 个姿态，覆盖平移、俯仰、偏航和滚转；标定板固定不动，相机刚性安装。

## 2. 求解关系

eye-in-hand 求解的是 `T_tool_camera`，使用经典手眼方程 `A X = X B`。离线脚本使用 OpenCV `calibrateHandEye` 的 Tsai 方法，并把结果写成独立 JSON；它不会修改 URDF、USD 或真机控制器。

## 3. 采集门槛

- 先完成相机内参和畸变标定；内参、分辨率或安装变化后必须重新确认；
- 真机采集需要具名授权、回零/已知起点、清场、急停、绿灯和唯一 CAN writer；
- 调整手部相机视角前，先执行完整回零并记录零位状态；随后可在新的具名姿态试验中同时移动多个声明关节，但每个目标角度、速度、保持时间和回程目标必须写入 manifest；
- 每个姿态保持到图像和 joint state 时间戳新鲜；姿态不能只绕同一根轴变化；
- 标定板在所有样本中保持固定，不能用移动目标替代固定 target。

## 4. 通过与发布

求解后检查每个样本的 `T_base_tool · T_tool_camera · T_camera_target` 在 base 中是否一致，报告 target 平移 MAE/p95/最大值（m）和旋转 MAE/p95/最大值（deg）。任务容差必须在 manifest 中声明；没有容差只能标记 `hand_eye_candidate`。用未参与求解的姿态留出验证后，才可生成版本化 TF override。

发布方向必须明确为 `tool -> camera` 或 `camera -> tool`，禁止仅凭 frame 名猜测。真实 TF 与 Isaac TF 分开保存；不得覆盖基础 URDF/USD。相机外参不能替代本体 `world -> base` 或 TCP 标定。

离线入口：

```bash
python3 /home/tangyuan/.codex/skills/openarm-sim2real-gap/scripts/hand_eye_calibrate.py \
  --input hand_eye_samples.json --output hand_eye_result.json
```
