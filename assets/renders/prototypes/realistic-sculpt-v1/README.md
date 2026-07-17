# Realistic Leo sculpt v1

Status: isolated project-owned identity candidate; not copied into runtime assets.

This candidate combines the cleanest retained project-owned quadruped sculpt with
four deterministic projections extracted from Leo's approved front, left, rear,
and right modeling turnaround. The images are packed into `leo-realistic.blend`;
no downloaded or third-party mesh is present.

What passed:

- all eight turntable views render as one coherent lion-cub silhouette;
- mechanical alpha, framing, and safety-edge QA passes;
- the front face, eyes, ear markings, coat, paws, and side anatomy derive from the
  approved project-owned realistic reference;
- multi-object normalization no longer detaches facial geometry.

What remains before rigging:

- reduce the remaining dorsal projection blend and improve the belly transition;
- refine the head, ear, paw, and tail geometry against the turnaround;
- produce a clean deformation topology and approve the final turntable at pet size.

`turntable-contact-sheet.png` is the review image. `identity-qa.json` records the
visual gate; `qa.json` records deterministic render checks.
