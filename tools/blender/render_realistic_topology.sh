#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
PYTHON=${PYTHON:-"$ROOT/.venv/bin/python"}
SOURCE=${LEO_REALISTIC_SOURCE:-"$ROOT/assets/source-3d/leo-realistic.blend"}
OUTPUT=${LEO_REALISTIC_TOPOLOGY_SOURCE:-"$ROOT/assets/source-3d/leo-realistic-topology.blend"}
WORK=${LEO_REALISTIC_TOPOLOGY_WORK:-"$ROOT/assets/renders/work/realistic-topology"}
SOURCE_PREVIEW="$WORK/source-preview"
CANDIDATE_PREVIEW="$WORK/candidate-preview"
TOPOLOGY_REPORT="$WORK/topology-report.json"
QA_REPORT="$WORK/qa.json"

mkdir -p "$SOURCE_PREVIEW" "$CANDIDATE_PREVIEW"

"$BLENDER" --background --factory-startup \
  --python "$ROOT/tools/blender/retopologize_realistic_leo.py" -- \
  --input "$SOURCE" \
  --output "$OUTPUT" \
  --report "$TOPOLOGY_REPORT" \
  --target-faces 16000 \
  --seed 7

for SPEC in "$SOURCE:$SOURCE_PREVIEW" "$OUTPUT:$CANDIDATE_PREVIEW"; do
  INPUT=${SPEC%%:*}
  PREVIEW=${SPEC#*:}
  "$BLENDER" --background --factory-startup \
    --python "$ROOT/tools/blender/preview_reconstructed_mesh.py" -- \
    --input "$INPUT" \
    --output-dir "$PREVIEW" \
    --preserve-materials \
    --samples 64
  "$PYTHON" "$ROOT/tools/blender/make_reconstruction_qa.py" \
    --render-dir "$PREVIEW"
done

"$PYTHON" "$ROOT/tools/blender/make_topology_qa.py" \
  --source-render-dir "$SOURCE_PREVIEW" \
  --candidate-render-dir "$CANDIDATE_PREVIEW" \
  --topology-report "$TOPOLOGY_REPORT" \
  --output "$QA_REPORT"

echo "LEO_REALISTIC_TOPOLOGY=$OUTPUT"
echo "LEO_REALISTIC_TOPOLOGY_PREVIEW=$CANDIDATE_PREVIEW"
echo "LEO_REALISTIC_TOPOLOGY_QA=$QA_REPORT"
