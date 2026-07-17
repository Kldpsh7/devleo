#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
PYTHON=${PYTHON:-"$ROOT/.venv/bin/python"}
SOURCE=${LEO_REALISTIC_TOPOLOGY_SOURCE:-"$ROOT/assets/source-3d/leo-realistic-topology.blend"}
OUTPUT=${LEO_REALISTIC_RIG_SOURCE:-"$ROOT/assets/source-3d/leo-realistic-rig.blend"}
WORK=${LEO_REALISTIC_RIG_WORK:-"$ROOT/assets/renders/work/realistic-rig"}
RIG_REPORT="$WORK/mechanical-qa.json"
DEFORMATIONS="$WORK/deformations"

mkdir -p "$WORK" "$DEFORMATIONS"

"$BLENDER" --background --factory-startup \
  --python "$ROOT/tools/blender/rig_realistic_leo.py" -- \
  --input "$SOURCE" \
  --output "$OUTPUT" \
  --report "$RIG_REPORT"

"$BLENDER" --background --factory-startup \
  --python "$ROOT/tools/blender/render_realistic_deformations.py" -- \
  --input "$OUTPUT" \
  --output-dir "$DEFORMATIONS" \
  --samples 64

"$PYTHON" "$ROOT/tools/blender/make_deformation_qa.py" \
  --render-dir "$DEFORMATIONS" \
  --rig-report "$RIG_REPORT"

echo "LEO_REALISTIC_RIG=$OUTPUT"
echo "LEO_REALISTIC_RIG_PREVIEW=$DEFORMATIONS/deformation-contact-sheet.png"
echo "LEO_REALISTIC_RIG_QA=$DEFORMATIONS/qa.json"
