# Leo 3D source

`leo.blend` is generated from `tools/blender/build_leo_scene.py`. The script is the
reviewable source of truth; the `.blend` file makes artist iteration convenient.

`leo-realistic-seed.blend` and `leo-realistic.blend` are the isolated realistic
rebuild inputs. The seed preserves the best project-owned quadruped reconstruction;
the refined source packs deterministic four-view texture projections extracted
from Leo's approved project-owned turnaround. Neither source is runtime-approved.

The current scene is the canonical model candidate with a quadruped armature, strand
fur, fixed lighting/camera, and a rigged laptop prop. It must not replace
`assets/approved` or packaged runtime art until every animation and explicit visual
approval are complete.

Rebuild it from the repository root:

```bash
blender --background --factory-startup \
  --python tools/blender/build_leo_scene.py -- \
  --output assets/source-3d/leo.blend
```

Rebuild and review the realistic identity candidate:

```bash
tools/blender/render_realistic_identity.sh
```
