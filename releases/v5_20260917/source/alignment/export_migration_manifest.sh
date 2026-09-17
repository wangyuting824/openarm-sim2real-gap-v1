#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$HOME/openarm_ws}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${2:-$ROOT/alignment/results/migration_manifest_${STAMP}}"

if [[ ! -d "$ROOT" ]]; then
  echo "workspace not found: $ROOT" >&2
  exit 1
fi

mkdir -p "$OUT"
MANIFEST="$OUT/manifest.txt"

{
  echo "generated_at=$(date --iso-8601=seconds)"
  echo "workspace=$ROOT"
  printf "git_commit="
  git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unavailable
  printf "git_branch="
  git -C "$ROOT" branch --show-current 2>/dev/null || echo unavailable
  echo
  echo "== top-level sizes =="
  du -sh "$ROOT"/alignment "$ROOT"/src "$ROOT"/dora "$ROOT"/ckpts "$ROOT"/build "$ROOT"/install "$ROOT"/log 2>/dev/null || true
  echo
  echo "== important paths =="
  for path in alignment/README.md alignment/results dora ckpts; do
    if [[ -e "$ROOT/$path" ]]; then
      printf "present\t%s\n" "$path"
    else
      printf "missing\t%s\n" "$path"
    fi
  done
  echo
  echo "== data file list (relative path, bytes) =="
  for dir in alignment/results dora ckpts; do
    if [[ -d "$ROOT/$dir" ]]; then
      find "$ROOT/$dir" -type f -printf "%P\t%s\n" | sed "s#^#$dir/#" | sort
    fi
  done
  echo
  echo "== config checksums =="
  for file in alignment/README.md alignment/mujoco_arm_offsets.json alignment/start_isaacsim_clean.sh alignment/start_real_openarm.sh; do
    if [[ -f "$ROOT/$file" ]]; then
      (cd "$ROOT" && sha256sum "$file")
    fi
  done
} > "$MANIFEST"

echo "Wrote $MANIFEST"
