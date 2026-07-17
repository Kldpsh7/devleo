# Blender production pipeline

Blender is a developer-only source and render dependency. Users installing Leo do
not need Blender; releases contain pre-rendered transparent sprites.

## Requirements

- Blender 5.2 LTS or later on the production workstation.
- Python 3.11+ with the project `art` dependencies for QA sheets and previews.
- No Blender add-ons are required for the first scene.

macOS setup:

```bash
brew install --cask blender
python3 -m venv .venv
.venv/bin/pip install -e '.[dev,art]'
```

## Full Idle prototype

```bash
tools/blender/render_idle.sh
```

The command rebuilds `assets/source-3d/leo.blend`, renders one neutral image and
twelve Idle frames into `assets/renders/work/idle-prototype`, removes variable PNG
metadata, clears transparent-pixel RGB, refreshes hashes, then creates:

- `manifest.json`: Blender/source checksums, render settings, timing, and frame hashes.
- `qa.json`: dimensions, alpha, safety-edge, and registration measurements.
- `contact-sheet.png`: all twelve frames for pose consistency review.
- `background-qa.png`: neutral render on light, dark, gray, and saturated backgrounds.
- `idle-preview.gif`: the loop at its intended slow six-frame-per-second timing.

Override paths without editing scripts:

```bash
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender \
PYTHON=.venv/bin/python \
LEO_BLEND_SOURCE=/tmp/leo.blend \
LEO_RENDER_OUTPUT=/tmp/leo-idle \
tools/blender/render_idle.sh
```

## Individual stages

Build only:

```bash
blender --background --factory-startup \
  --python tools/blender/build_leo_scene.py -- \
  --output assets/source-3d/leo.blend
```

Render only:

```bash
blender --background assets/source-3d/leo.blend \
  --python tools/blender/render_leo_idle.py -- \
  --output-dir assets/renders/work/idle-prototype
.venv/bin/python tools/blender/canonicalize_renders.py \
  --render-dir assets/renders/work/idle-prototype
```

Regenerate QA only:

```bash
.venv/bin/python tools/blender/make_render_qa.py \
  --render-dir assets/renders/work/idle-prototype
```

## Approval gate

This prototype is intentionally isolated from the live pet. Approval requires the
same Leo identity in every frame, a readable closed laptop lid at minimum size,
animal anatomy, transparent clean edges, no clipping, stable paws/baseline, and a
slow cohesive loop. Only approved renders are exported once per runtime density.
