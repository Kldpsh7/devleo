#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BLENDER="${BLENDER:-$(command -v blender || true)}"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
SOURCE="${LEO_BLEND_SOURCE:-$ROOT/assets/source-3d/leo.blend}"
OUTPUT="${LEO_GAZE_OUTPUT:-$ROOT/assets/renders/work/gaze-directions}"

if [[ -z "$BLENDER" ]]; then
  echo "Blender was not found. Install it with: brew install --cask blender" >&2
  exit 1
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment missing. Install the project with: .venv/bin/pip install -e '.[dev,art]'" >&2
  exit 1
fi

"$BLENDER" --background "$SOURCE" \
  --python "$ROOT/tools/blender/render_gaze_directions.py" -- \
  --output-dir "$OUTPUT"
"$PYTHON" "$ROOT/tools/blender/canonicalize_renders.py" --render-dir "$OUTPUT"
"$PYTHON" "$ROOT/tools/blender/make_gaze_qa.py" --render-dir "$OUTPUT"

echo "Review: $OUTPUT/gaze-directions.png"
