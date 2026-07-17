#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BLENDER="${BLENDER:-$(command -v blender || true)}"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
SOURCE="${LEO_BLEND_SOURCE:-$ROOT/assets/source-3d/leo.blend}"
OUTPUT="${LEO_RENDER_OUTPUT:-$ROOT/assets/renders/work/idle-prototype}"

if [[ -z "$BLENDER" ]]; then
  echo "Blender was not found. Install it with: brew install --cask blender" >&2
  exit 1
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment missing. Run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev,art]'" >&2
  exit 1
fi

mkdir -p "$(dirname "$SOURCE")" "$OUTPUT"
"$BLENDER" --background --factory-startup \
  --python "$ROOT/tools/blender/build_leo_scene.py" -- \
  --output "$SOURCE"
"$BLENDER" --background "$SOURCE" \
  --python "$ROOT/tools/blender/render_leo_idle.py" -- \
  --output-dir "$OUTPUT"
"$PYTHON" "$ROOT/tools/blender/canonicalize_renders.py" --render-dir "$OUTPUT"
"$PYTHON" "$ROOT/tools/blender/make_render_qa.py" --render-dir "$OUTPUT"

echo "Scene: $SOURCE"
echo "Review: $OUTPUT/contact-sheet.png"
echo "Motion: $OUTPUT/idle-preview.gif"
