#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
SOURCE_ROOT="${LEO_RENDER_SOURCE_ROOT:-$ROOT/assets/renders/work}"
OUTPUT="${LEO_RUNTIME_EXPORT_OUTPUT:-$ROOT/assets/renders/work/runtime-export-v1}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment missing. Install the project with: .venv/bin/pip install -e '.[dev,art]'" >&2
  exit 1
fi

"$PYTHON" "$ROOT/tools/blender/export_runtime_assets.py" \
  --source-root "$SOURCE_ROOT" \
  --output-dir "$OUTPUT"

echo "Review: $OUTPUT"
