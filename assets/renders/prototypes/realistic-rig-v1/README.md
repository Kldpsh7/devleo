# Realistic Leo quadruped rig candidate v1

Status: rejected as a visual candidate. The rig mechanics remain a useful
isolated experiment, but the projected face is distorted in neutral and posed
front, profile, and three-quarter views. Nothing from this candidate was copied
into runtime assets.

Generated with:

```bash
tools/blender/render_realistic_rig.sh
```

Mechanical checks that passed:

- 22-bone feline hierarchy with 21 deform bones;
- every one of the 15,661 mesh vertices has a deform weight;
- no empty deform group and no vertex with more than four influences;
- smooth anatomical weight localization at neck, shoulders, hips, and tail base;
- twelve diagnostic renders covering neutral, head yaw, head pitch, foreleg
  lift, hind step, and tail curl from side and front views;
- no transparent frame, safety-edge contact, opaque corner, surface tear,
  detached region, or hard weight seam;
- projected alpha area remains within 0.34-3.41% of the matching neutral view.

Visual check that failed:

- the front/side/rear texture projections are blended over facial geometry that
  does not match the source cub's skull, eyes, muzzle, or ears. This produces
  duplicated and stretched facial features from every viewing direction.

The retained source is `assets/source-3d/leo-realistic-rig.blend`.
`deformation-contact-sheet.png` is the visual checkpoint, `mechanical-qa.json`
records rig and weight coverage, and `qa.json` records render measurements.

These are deliberately stronger diagnostic poses, not reusable state animation.
Animation work is paused. The next gate is a rebuilt neutral head that passes
front, profile, and both three-quarter visual review before it is rigged.
