# Leo 3D source

`leo.blend` is generated from `tools/blender/build_leo_scene.py`. The script is the
reviewable source of truth; the `.blend` file makes artist iteration convenient.

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
