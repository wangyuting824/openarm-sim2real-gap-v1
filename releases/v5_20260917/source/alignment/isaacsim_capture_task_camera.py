import builtins
import csv
import json
import time
from pathlib import Path

import numpy as np
import omni.kit.app
import omni.timeline
import omni.usd
from pxr import Gf, UsdGeom

CAMERA_PATH = "/World/openarm_task_camera"
CAMERA_ID = "ceiling"
POSITION_M = (0.0, 0.0, 1.20)
LOOK_AT_M = (0.0, 0.0, 0.25)
RESOLUTION = (640, 480)
FPS = 1.0
DURATION_S = 10.0
FOCAL_LENGTH_MM = 24.0
HORIZONTAL_APERTURE_MM = 20.955
VERTICAL_APERTURE_MM = 15.291
RESULT_ROOT = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_migration")


def look_at_matrix(position, target):
    pos = Gf.Vec3d(*position)
    target = Gf.Vec3d(*target)
    forward = target - pos
    forward.Normalize()

    up_hint = Gf.Vec3d(0.0, 1.0, 0.0)
    if abs(Gf.Dot(forward, up_hint)) > 0.99:
        up_hint = Gf.Vec3d(1.0, 0.0, 0.0)

    right = Gf.Cross(forward, up_hint)
    right.Normalize()
    up = Gf.Cross(right, forward)

    matrix = Gf.Matrix4d(1.0)
    matrix.SetRow(0, Gf.Vec4d(right[0], right[1], right[2], 0.0))
    matrix.SetRow(1, Gf.Vec4d(up[0], up[1], up[2], 0.0))
    matrix.SetRow(2, Gf.Vec4d(-forward[0], -forward[1], -forward[2], 0.0))
    matrix.SetRow(3, Gf.Vec4d(pos[0], pos[1], pos[2], 1.0))
    return matrix


old = getattr(builtins, "_openarm_task_camera_capture", None)
if old is not None:
    old["sub"] = None

stage = omni.usd.get_context().get_stage()
if stage is None:
    raise RuntimeError("No USD stage is open")

meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(stage))
camera = UsdGeom.Camera.Define(stage, CAMERA_PATH)
camera.GetFocalLengthAttr().Set(FOCAL_LENGTH_MM)
camera.GetHorizontalApertureAttr().Set(HORIZONTAL_APERTURE_MM)
camera.GetVerticalApertureAttr().Set(VERTICAL_APERTURE_MM)

xform = UsdGeom.Xformable(camera.GetPrim())
xform.ClearXformOpOrder()
xform.AddTransformOp().Set(
    look_at_matrix(
        tuple(v / meters_per_unit for v in POSITION_M),
        tuple(v / meters_per_unit for v in LOOK_AT_M),
    )
)

try:
    from isaacsim.sensors.camera import Camera
except ImportError:
    from omni.isaac.sensor import Camera

sensor = Camera(
    prim_path=CAMERA_PATH,
    name="openarm_task_camera",
    frequency=FPS,
    resolution=RESOLUTION,
)

session_id = "isaac_task_camera_" + time.strftime("%Y%m%d_%H%M%S")
out = RESULT_ROOT / session_id / "vision"
frames_dir = out / "frames"
frames_dir.mkdir(parents=True, exist_ok=False)

fx = FOCAL_LENGTH_MM / HORIZONTAL_APERTURE_MM * RESOLUTION[0]
fy = FOCAL_LENGTH_MM / VERTICAL_APERTURE_MM * RESOLUTION[1]

camera_info = {
    "camera_id": CAMERA_ID,
    "frame_id": CAMERA_PATH,
    "width": RESOLUTION[0],
    "height": RESOLUTION[1],
    "fps": FPS,
    "distortion_model": "plumb_bob",
    "D": [0.0] * 5,
    "K": [fx, 0.0, RESOLUTION[0] / 2, 0.0, fy, RESOLUTION[1] / 2, 0.0, 0.0, 1.0],
    "world_position_m": list(POSITION_M),
    "look_at_m": list(LOOK_AT_M),
    "focal_length_mm": FOCAL_LENGTH_MM,
    "horizontal_aperture_mm": HORIZONTAL_APERTURE_MM,
    "vertical_aperture_mm": VERTICAL_APERTURE_MM,
}
(out / "camera_info.json").write_text(
    json.dumps(camera_info, indent=2) + "\n", encoding="utf-8"
)

timeline = omni.timeline.get_timeline_interface()
timeline.play()

state = {
    "sub": None,
    "initialized": False,
    "start": None,
    "last": None,
    "rows": [],
    "count": 0,
    "finished": False,
    "error": None,
}


def finish():
    if state["finished"]:
        return

    state["finished"] = True

    with (out / "frame_timestamps.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["frame_index", "sim_time_s", "wall_time_s", "file"],
        )
        writer.writeheader()
        writer.writerows(state["rows"])

    metrics = {
        "session_id": session_id,
        "source": "isaac_sim",
        "frame_count": state["count"],
        "camera_info": "camera_info.json",
        "frame_timestamps": "frame_timestamps.csv",
        "frames_dir": "frames",
        "capture_error": state["error"],
    }
    result = out / "camera_capture_metrics.json"
    result.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    state["sub"] = None
    print("OPENARM_TASK_CAMERA_COMPLETE")
    print("RESULT=" + str(result))
    print(json.dumps(metrics, indent=2))


def on_update(_event):
    try:
        now = time.monotonic()

        if not state["initialized"]:
            sensor.initialize()
            state["initialized"] = True
            state["start"] = now
            print("OPENARM_TASK_CAMERA_READY resolution=%s fps=%.1f" % (RESOLUTION, FPS))

        if now - state["start"] >= DURATION_S:
            finish()
            return

        if state["last"] is not None and now - state["last"] < 1.0 / FPS:
            return

        

        from PIL import Image

        filename = "frame_%06d.png" % state["count"]
        Image.fromarray(rgba[..., :3].astype(np.uint8), "RGB").save(
            frames_dir / filename
        )

        state["rows"].append({
            "frame_index": state["count"],
            "sim_time_s": float(timeline.get_current_time()),
            "wall_time_s": now,
            "file": "frames/" + filename,
        })
        state["count"] += 1
        state["last"] = now

        if state["count"] == 1:
            print("OPENARM_TASK_CAMERA_FRAME_CAPTURED")

    except Exception as error:
        state["error"] = repr(error)
        finish()
        print("OPENARM_TASK_CAMERA_ERROR " + repr(error))


state["sub"] = (
    omni.kit.app.get_app()
    .get_update_event_stream()
    .create_subscription_to_pop(on_update)
)
builtins._openarm_task_camera_capture = state

print("OPENARM_TASK_CAMERA_ARMED path=" + CAMERA_PATH)