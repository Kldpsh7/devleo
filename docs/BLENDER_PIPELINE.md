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

### Realistic identity reconstruction gate

The realistic rebuild is evaluated independently before rigging or laptop work.
Its approved modeling references and rejected reconstruction evidence live in
`assets/renders/prototypes/realistic-model-v1/`.

Render an eight-view preview for any reconstructed GLB:

```bash
blender --background --factory-startup \
  --python tools/blender/preview_reconstructed_mesh.py -- \
  --input /path/to/candidate.glb \
  --output-dir assets/renders/work/realistic-mesh/candidate \
  --rotation-x -90 \
  --smooth-factor 0.55 \
  --smooth-iterations 12
.venv/bin/python tools/blender/make_reconstruction_qa.py \
  --render-dir assets/renders/work/realistic-mesh/candidate
```

This gate verifies orientation, material color, full-turn anatomy, transparency,
and framing. A mechanical QA pass does not approve the model: front, profile, and
rear views must all match the canonical turnaround before the mesh is retained as
the rig source.

Rebuild the current project-owned candidate, its deterministic four-view
projections, eight-view preview, and mechanical QA in one command:

```bash
tools/blender/render_realistic_identity.sh
```

The checkpoint is stored in `assets/source-3d/leo-realistic.blend`, with review
evidence in `assets/renders/prototypes/realistic-sculpt-v1/`. It is still isolated
from the runtime while head/ear/paw topology and the dorsal projection transition
remain under review.

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

Render the approved pose contract as full motion candidates:

```bash
tools/blender/render_core_animations.sh
```

The command produces 12-frame Waiting, 16-frame Working, 12-frame Review, and
14-frame Failure sequences. QA records alpha, safety margins, baseline and center
registration, unique motion frames, contact sheets, and real-time GIF previews.

Approve gaze cardinals before rendering intermediate directions:

```bash
tools/blender/render_gaze_cardinals.sh
tools/blender/render_gaze_directions.sh
```

The full gaze command renders 16 clockwise directions from `000` up through
`337.5` up-left. It keeps the lower body and closed laptop registered, emits
1152x1248 transparent masters, a normal-size loop, and an isolated 1536x2288 QA
atlas for the hatch-pet direction semantics, continuity, and blind-review gates.

Render the quadrupedal locomotion family after gaze approval:

```bash
tools/blender/render_locomotion.sh
```

This produces 12-frame left/right Walk and playful pounce-Run candidates from the
canonical source without modifying it. The closed laptop remains secured against
Leo's flank while deterministic QA checks master alpha, registration, cadence, and
the Run airborne phase.

Render one-shot Wave and Jump gestures after locomotion approval:

```bash
tools/blender/render_gestures.sh
```

Wave raises a complete seated front-leg chain. Jump uses the quadrupedal carry pose
for a four-paw spring with an airborne phase. Both return exactly to their source
pose and keep the laptop closed.

Render seated-to-roaming transition candidates after locomotion approval:

```bash
tools/blender/render_transitions.sh
```

This produces 20-frame Idle-to-Walk and exact reversed Walk-to-Idle sequences for
both directions. Leo crouches and lifts the closed laptop into or out of the
approved flank carry so a roaming cycle does not snap between seated and moving
poses. The transition wrapper registers each frame to the canonical master ground
line before generating QA artifacts.

Export the approved Blender families into isolated runtime density tiers:

```bash
tools/blender/export_runtime_assets.sh
```

The exporter produces full 1×, 2×, and 4× frame families plus a Codex-compatible
8×11 v2 atlas at each density. It samples only the fixed compatibility atlas
counts; full Blender frame counts remain available beside the atlases. No output
is copied into the live package before final export QA and visual approval.

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
