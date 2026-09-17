"""Record Isaac-native camera prim parameters and world poses (read-only)."""
import json
import time
from pathlib import Path

import omni.usd
from pxr import Usd, UsdGeom

stage = omni.usd.get_context().get_stage()
if stage is None:
    raise RuntimeError("No USD stage is open")

root = Path("/home/tangyuan/openarm_ws/alignment/results/isaacsim_migration")
session = "isaac_camera_" + time.strftime("%Y%m%d_%H%M%S")
out = root / session / "vision"
out.mkdir(parents=True, exist_ok=False)
meters = float(UsdGeom.GetStageMetersPerUnit(stage))
cameras = []

for prim in stage.Traverse():
    if prim.GetTypeName() != "Camera":
        continue
    xform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    t = xform.ExtractTranslation()
    q = xform.ExtractRotationQuat()
    imag = q.GetImaginary()
    def value(name):
        attr = prim.GetAttribute(name)
        return attr.Get() if attr and attr.HasValue() else None
    cameras.append({
        "prim_path": str(prim.GetPath()),
        "world_position_m": [float(t[i]) * meters for i in range(3)],
        "world_orientation_xyzw": [float(imag[i]) for i in range(3)] + [float(q.GetReal())],
        "focal_length_mm": value("focalLength"),
        "horizontal_aperture_mm": value("horizontalAperture"),
        "vertical_aperture_mm": value("verticalAperture"),
        "clipping_range": value("clippingRange"),
        "projection": value("projection"),
        "resolution": None,
        "fps": None,
        "distortion": "not_configured",
    })

result = {
    "session_id": session,
    "source": "isaac_sim",
    "stage_meters_per_unit": meters,
    "camera_count": len(cameras),
    "cameras": cameras,
    "image_frames": "not_recorded",
    "camera_info": "not_recorded",
    "exposure_lighting_occlusion": "not_configured",
}
(out / "camera_params.json").write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
print("OPENARM_CAMERA_PARAMS_COMPLETE count=%d" % len(cameras))
print("RESULT=" + str(out / "camera_params.json"))
print(json.dumps(result, indent=2, default=str))
