#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BLENDER="${BLENDER:-$(command -v blender || true)}"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
SOURCE="${LEO_BLEND_SOURCE:-$ROOT/assets/source-3d/leo.blend}"
OUTPUT="${LEO_CORE_OUTPUT:-$ROOT/assets/renders/work/core-animations}"

if [[ -z "$BLENDER" ]]; then
  echo "Blender was not found. Install it with: brew install --cask blender" >&2
  exit 1
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment missing. Install the project with: .venv/bin/pip install -e '.[dev,art]'" >&2
  exit 1
fi

"$BLENDER" --background --factory-startup \
  --python "$ROOT/tools/blender/build_leo_scene.py" -- \
  --output "$SOURCE"
"$BLENDER" --background "$SOURCE" \
  --python "$ROOT/tools/blender/render_core_animations.py" -- \
  --output-dir "$OUTPUT"
"$PYTHON" "$ROOT/tools/blender/canonicalize_renders.py" --render-dir "$OUTPUT"
"$PYTHON" "$ROOT/tools/blender/make_core_animation_qa.py" --render-dir "$OUTPUT"

echo "Review: $OUTPUT"
