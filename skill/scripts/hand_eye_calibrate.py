#!/usr/bin/env python3
"""Offline eye-in-hand calibration; never connects to ROS or hardware."""
import argparse, json
from pathlib import Path
import numpy as np

def inv(T):
    R, t = T[:3, :3], T[:3, 3]
    out = np.eye(4); out[:3, :3] = R.T; out[:3, 3] = -R.T @ t
    return out

def load_pose(x):
    T = np.asarray(x["matrix"], dtype=float) if "matrix" in x else np.block([[np.asarray(x["R"], dtype=float), np.asarray(x["t"], dtype=float).reshape(3, 1)], [np.zeros((1, 3)), np.ones((1, 1))]])
    if T.shape != (4, 4) or not np.all(np.isfinite(T)): raise ValueError("pose must be a finite 4x4 matrix or R/t pair")
    return T

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--input", required=True); ap.add_argument("--output", required=True); ap.add_argument("--method", default="tsai", choices=["tsai", "park", "horaud", "andreff", "daniilidis"]); args = ap.parse_args()
    try: import cv2
    except ImportError as exc: raise SystemExit("opencv-python is required for offline hand-eye solving") from exc
    data = json.loads(Path(args.input).read_text(encoding="utf-8")); samples = data.get("samples", [])
    if len(samples) < 4: raise SystemExit("at least 4 pose pairs are required; 12-30 diverse poses are recommended")
    base_tool = [load_pose(s["T_base_tool"]) for s in samples]; cam_target = [load_pose(s["T_camera_target"]) for s in samples]
    g2b, t2c = [inv(T) for T in base_tool], [inv(T) for T in cam_target]
    methods = {"tsai": cv2.CALIB_HAND_EYE_TSAI, "park": cv2.CALIB_HAND_EYE_PARK, "horaud": cv2.CALIB_HAND_EYE_HORAUD, "andreff": cv2.CALIB_HAND_EYE_ANDREFF, "daniilidis": cv2.CALIB_HAND_EYE_DANIILIDIS}
    Rcg, tcg = cv2.calibrateHandEye([T[:3,:3] for T in g2b], [T[:3,3:4] for T in g2b], [T[:3,:3] for T in t2c], [T[:3,3:4] for T in t2c], method=methods[args.method])
    tool_camera = np.eye(4); tool_camera[:3,:3] = Rcg; tool_camera[:3,3] = tcg.reshape(3)
    target_in_base = [T @ tool_camera @ C for T, C in zip(base_tool, cam_target)]; ref = target_in_base[0]
    trans = [float(np.linalg.norm(T[:3,3] - ref[:3,3])) for T in target_in_base]
    angles = [float(np.degrees(np.linalg.norm(cv2.Rodrigues(ref[:3,:3].T @ T[:3,:3])[0]))) for T in target_in_base]
    result = {"schema_version": 1, "kind": "openarm_hand_eye_candidate", "mode": "eye_in_hand", "method": args.method, "sample_count": len(samples), "T_tool_camera": tool_camera.tolist(), "target_in_base_consistency": {"translation_mae_m": float(np.mean(trans)), "translation_p95_m": float(np.percentile(trans,95)), "translation_max_m": float(np.max(trans)), "rotation_mae_deg": float(np.mean(angles)), "rotation_p95_deg": float(np.percentile(angles,95)), "rotation_max_deg": float(np.max(angles))}, "input": str(Path(args.input)), "status": "hand_eye_candidate", "writes_tf": False, "hardware_commands_sent": False}
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8"); print(json.dumps(result, indent=2))

if __name__ == "__main__": main()
