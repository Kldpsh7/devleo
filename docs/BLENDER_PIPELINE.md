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
- `identity-turnaround.png`: front, three-quarter, and profile geometry review.
- `scale-qa.png`: actual-size 0.55×, 0.75×, 1×, and 1.25× readability matrix.
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

Render the core laptop/state pose contract:

```bash
tools/blender/render_state_poses.sh
```

This produces isolated Idle, Waiting, Working, Review, and Failure poses. The laptop
control is closed at 0°, half-open at 48°, and fully open at 96°. These still-pose
gates must pass before their individual motion loops and transitions are rendered.

## Approval gate

This prototype is intentionally isolated from the live pet. Approval requires the
same Leo identity in every frame, a readable closed laptop lid at minimum size,
animal anatomy, transparent clean edges, no clipping, stable paws/baseline, and a
slow cohesive loop. Only approved renders are exported once per runtime density.

## Canonical scene contract

The Phase 1 source candidate contains a nineteen-bone quadruped rig: root, pelvis,
spine, neck, head, bilateral foreleg/hind-leg chains, a three-bone tail, and a
non-deforming laptop prop bone. Eighteen strand-fur systems cover the visible coat
parts; the transparent render uses a fixed orthographic camera and three-area-light
setup. The render command rejects missing objects or bones before producing assets.

Identity review uses front, three-quarter, and profile renders. Runtime readability is
checked at 0.55×, 0.75×, 1×, and 1.25× on light and dark backgrounds. These gates do
not authorize copying the candidate into the packaged runtime asset tree.
