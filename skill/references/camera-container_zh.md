# 相机 ROS 容器启动规则

skill 不假定固定容器名或固定镜像。手部相机 USB 接在哪台主机，就必须在那台主机启动驱动或启动能访问该主机 `/dev` 的容器；Isaac 主机上的 ROS 容器不能自动访问真机主机的 USB。

在相机主机执行：

```bash
OPENARM_CAMERA_IMAGE=<包含相机驱动的镜像> \
OPENARM_CAMERA_CONTAINER=openarm_camera_ros \
bash alignment/start_openarm_camera_container.sh
```

容器必须使用 `--network host`，并映射 `/dev` 与 `/dev/bus/usb`。进入后先检查：

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42 ROS_LOCALHOST_ONLY=0 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
lsusb
v4l2-ctl --list-devices 2>/dev/null || true
ros2 pkg list | grep -E 'realsense|usb_cam|camera'
```

## 当前主机的已观测设备映射

在 2026-09-20 的真机主机上，`lsusb` 枚举到 Arducam B0495 和 RealSense D435i，并出现 `/dev/video0`--`/dev/video7`。当前格式探测显示：

- `/dev/video0`：Arducam 的 YUYV 彩色流，支持 1920×1200；
- `/dev/video2`：RealSense Z16 深度流；
- `/dev/video4`：RealSense GREY 灰度/红外流；
- `/dev/video6`：RealSense YUYV 彩色流；
- 其余节点可能是 metadata 或辅助流，必须用 `v4l2-ctl --list-devices` 和相机序列号确认。

不能把 `/dev/video0` 或 `/dev/video6` 自动命名为“右手相机”。右手相机必须通过物理安装位置、预览画面、USB serial 和 manifest 确认；更换 USB 插拔顺序后 video 编号可能变化。

本轮已确认的 Arducam 启动路径：`/dev/video0` 使用 `YUYV`、`1920x1200` 可采集；ROS `v4l2_camera` 发布 `/right_hand_camera/image_raw` 与 `/right_hand_camera/camera_info`，实测图像约 38 Hz。若 `rqt_image_view` 显示灰白，先停止 ROS 节点，用 `ffplay -f v4l2 -input_format yuyv422 -video_size 1920x1200 -framerate 30 /dev/video0` 验证原始画面；原始画面正常后再重启 ROS/rqt。当前 `camera_info` 仍因缺少 Arducam YAML 只能标记 `intrinsics_missing`，不得用于手眼求解。

只有镜像内存在对应驱动，才能启动驱动。例如 RealSense 驱动存在时：

```bash
ros2 launch realsense2_camera rs_launch.py enable_color:=true enable_depth:=true
```

启动后必须看到图像和 `camera_info` 话题，再进行手眼标定：

```bash
ros2 topic list | grep -E 'image|camera_info'
ros2 topic hz <右手相机图像话题>
```

`ros:jazzy` 基础镜像不包含 RealSense 或 Arducam 驱动，不能把它当成相机镜像。镜像、驱动版本、相机序列号、分辨率和 frame 名必须写入 session manifest。容器启动本身不等于相机已发布；没有新鲜图像和 CameraInfo 时，手眼采集停止。
