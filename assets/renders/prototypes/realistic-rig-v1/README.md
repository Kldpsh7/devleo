# Realistic Leo quadruped rig candidate v1

Status: isolated project-owned deformation candidate; not copied into runtime
assets and not treated as finished animation.

Generated with:

```bash
tools/blender/render_realistic_rig.sh
```

What passed:

- 22-bone feline hierarchy with 21 deform bones;
- every one of the 15,661 mesh vertices has a deform weight;
- no empty deform group and no vertex with more than four influences;
- smooth anatomical weight localization at neck, shoulders, hips, and tail base;
- twelve renders covering neutral, head yaw, head pitch, foreleg lift, hind step,
  and tail curl from side and front views;
- no transparent frame, safety-edge contact, opaque corner, surface tear, detached
  region, or hard weight seam;
- projected alpha area remains within 0.34-3.41% of the matching neutral view.

The retained source is `assets/source-3d/leo-realistic-rig.blend`.
`deformation-contact-sheet.png` is the visual checkpoint, `mechanical-qa.json`
records rig and weight coverage, and `qa.json` records render measurements.

These are deliberately stronger diagnostic poses, not reusable state animation.
The next gate is production pose controls and a slow neutral/idle loop while the
realistic model remains isolated from the live pet.
