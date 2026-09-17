"""Export the currently open Isaac Sim stage without modifying it.

Run once in Isaac Sim's Script Editor.  It writes a readable USDA, a flattened
USDC, and (when supported by the installed USD build) a self-contained USDZ
package under ``alignment/exports``.  The JSON manifest identifies the source
root layer and hashes each artifact so it can be shared and audited.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import omni.usd
from pxr import UsdGeom, UsdUtils


EXPORT_ROOT = Path("/home/tangyuan/openarm_ws/alignment/exports")
EXPORT_NAME = "openarm_isaacsim_scene_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_stage() -> None:
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open")

    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    usda = EXPORT_ROOT / f"{EXPORT_NAME}.usda"
    usdc = EXPORT_ROOT / f"{EXPORT_NAME}.usdc"
    usdz = EXPORT_ROOT / f"{EXPORT_NAME}.usdz"
    manifest_path = EXPORT_ROOT / f"{EXPORT_NAME}.manifest.json"

    # Stage.Export writes a composed, flattened snapshot; the open stage and
    # its root layer remain unchanged.
    if not stage.Export(str(usda)):
        raise RuntimeError(f"Failed to export USDA: {usda}")
    if not stage.Export(str(usdc)):
        raise RuntimeError(f"Failed to export USDC: {usdc}")

    package_error = None
    if usdz.exists():
        usdz.unlink()
    try:
        packaged = UsdUtils.CreateNewUsdzPackage(str(usdc), str(usdz))
        if not packaged:
            package_error = "UsdUtils.CreateNewUsdzPackage returned false"
    except Exception as error:
        package_error = repr(error)

    artifacts = []
    for path in (usda, usdc, usdz):
        if path.is_file():
            artifacts.append({
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    manifest = {
        "schema_version": 1,
        "kind": "openarm_isaacsim_stage_export",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_root_layer": str(stage.GetRootLayer().identifier),
        "default_prim": str(stage.GetDefaultPrim().GetPath()) if stage.GetDefaultPrim() else None,
        "meters_per_unit": float(UsdGeom.GetStageMetersPerUnit(stage)),
        "up_axis": str(UsdGeom.GetStageUpAxis(stage)),
        "artifacts": artifacts,
        "usdz_package_error": package_error,
        "note": "USDA/USDC are flattened snapshots. USDZ is the preferred handoff artifact when created successfully.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("OPENARM_USD_EXPORT_COMPLETE")
    print("MANIFEST=" + str(manifest_path))
    print(json.dumps(manifest, indent=2))


export_stage()
