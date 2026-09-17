#!/usr/bin/env bash
# Prepare a self-contained Isaac Sim import copy of the OpenArm v2.0 URDF.
# The source URDF is preserved.  Only package:// mesh URIs are rewritten to
# file:// URIs that the Isaac URDF importer can resolve without ROS.
set -euo pipefail

WORKSPACE="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SOURCE_URDF="$WORKSPACE/alignment/openarm_v20_reference.urdf"
DESCRIPTION_ROOT="$WORKSPACE/src/openarm_description"
OUTPUT_DIR="$WORKSPACE/alignment/isaacsim_assets/openarm_v20_import"
OUTPUT_URDF="$OUTPUT_DIR/openarm_v20_isaac.urdf"

[[ -f "$SOURCE_URDF" ]] || { echo "Missing source URDF: $SOURCE_URDF" >&2; exit 1; }
[[ -d "$DESCRIPTION_ROOT/assets" ]] || { echo "Missing description assets: $DESCRIPTION_ROOT/assets" >&2; exit 1; }

mkdir -p "$OUTPUT_DIR"

python3 - "$SOURCE_URDF" "$OUTPUT_URDF" "$DESCRIPTION_ROOT" <<'PY'
from pathlib import Path
import sys

source, destination, description_root = map(Path, sys.argv[1:])
text = source.read_text()
old = "package://openarm_description/"
new = description_root.as_uri() + "/"
if old not in text:
    raise SystemExit(f"No {old} references found in {source}")
destination.write_text(text.replace(old, new))
print(f"Wrote {destination}")
print(f"Replaced {text.count(old)} mesh URI(s) with {new}")
PY

echo
echo "Import this file in the Isaac Sim GUI:"
echo "  $OUTPUT_URDF"
echo "Suggested USD output directory:"
echo "  $OUTPUT_DIR"
