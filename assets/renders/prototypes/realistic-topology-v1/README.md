# Realistic Leo clean-topology candidate v1

Status: isolated project-owned modeling candidate; not copied into runtime assets.

Generated with:

```bash
tools/blender/render_realistic_topology.sh
```

What passed:

- source face count reduced from 79,512 triangles to 15,659 quads;
- one connected manifold surface with zero boundary edges, zero non-manifold
  edges, and zero isolated vertices;
- all four project-owned projection images remain packed in the Blender source;
- all eight candidate views pass alpha, framing, and safety-edge QA;
- minimum eight-view silhouette IoU against the approved identity is 0.996264;
- maximum per-channel mean absolute render difference is 2.372 on a 0-255 scale.

The retained source is `assets/source-3d/leo-realistic-topology.blend`.
`turntable-contact-sheet.png` is the visual checkpoint and `qa.json` contains the
mechanical plus identity-preservation evidence.

This pass proves clean manifold quad topology and surface identity preservation.
It does not yet prove joint edge flow or deformation quality. The next gate is a
minimal feline armature with shoulder, hip, paw, neck, and tail deformation tests;
head, ear, paw, tail, and belly anatomy still require visual refinement before the
model can replace runtime art.
