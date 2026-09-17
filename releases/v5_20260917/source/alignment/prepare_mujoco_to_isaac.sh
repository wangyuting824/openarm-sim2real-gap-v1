#!/usr/bin/env bash
# Snapshot the vendor's complete MuJoCo v2 asset tree before importing it
# into Isaac Sim's MJCF importer. The source is never changed.
set -euo pipefail

WORKSPACE="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DEST_PARENT="$WORKSPACE/alignment/isaacsim_assets"
DEST="$DEST_PARENT/mujoco_v2"

CELL_XML="$(find "$WORKSPACE/dora" -type f -path '*/share/openarm_mujoco/v2/cell/cell.xml' -print -quit 2>/dev/null || true)"
if [[ -z "$CELL_XML" ]]; then
  cat >&2 <<EOF
Cannot find the vendor MuJoCo v2 assets below:
  $WORKSPACE/dora

Copy the source package that contains share/openarm_mujoco/v2 first.
EOF
  exit 1
fi

SOURCE="$(cd "$(dirname "$CELL_XML")/.." && pwd)"
mkdir -p "$DEST_PARENT"

if [[ -e "$DEST" ]]; then
  echo "Destination already exists; keeping it unchanged: $DEST" >&2
  echo "Remove or rename it manually only if you explicitly want a new snapshot." >&2
  exit 2
fi

cp -a "$SOURCE" "$DEST"

echo "Vendor MuJoCo v2 source: $SOURCE"
echo "Isaac import snapshot:    $DEST"
echo "First MJCF to import:     $DEST/cell/cell.xml"
echo "Optional demo scene:      $DEST/cell/demo.xml"
