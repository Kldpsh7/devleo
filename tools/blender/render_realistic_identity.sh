#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
PYTHON=${PYTHON:-"$ROOT/.venv/bin/python"}
REFERENCE=${LEO_REALISTIC_REFERENCE:-"$ROOT/assets/source/realistic-identity-reference/cardinal-turnaround.png"}
SEED=${LEO_REALISTIC_SEED:-"$ROOT/assets/source-3d/leo-realistic-seed.blend"}
SOURCE=${LEO_REALISTIC_SOURCE:-"$ROOT/assets/source-3d/leo-realistic.blend"}
WORK=${LEO_REALISTIC_WORK:-"$ROOT/assets/renders/work/realistic-identity"}
TEXTURES="$WORK/turnaround-textures"
PREVIEW="$WORK/preview"

mkdir -p "$TEXTURES" "$PREVIEW"

"$PYTHON" "$ROOT/tools/blender/extract_turnaround_textures.py" \
  --input "$REFERENCE" \
  --output-dir "$TEXTURES"

"$BLENDER" --background --factory-startup \
  --python "$ROOT/tools/blender/refine_realistic_leo.py" -- \
  --input "$SEED" \
  --output "$SOURCE" \
  --textures-dir "$TEXTURES"

"$BLENDER" --background --factory-startup \
  --python "$ROOT/tools/blender/preview_reconstructed_mesh.py" -- \
  --input "$SOURCE" \
  --output-dir "$PREVIEW" \
  --preserve-materials \
  --samples 64

"$PYTHON" "$ROOT/tools/blender/make_reconstruction_qa.py" \
  --render-dir "$PREVIEW"

echo "LEO_REALISTIC_IDENTITY=$SOURCE"
echo "LEO_REALISTIC_PREVIEW=$PREVIEW"
