# Realistic Leo identity gate v1

This checkpoint replaces the rejected primitive-model visual target with a
realistic young African lion cub reference. It does **not** replace the live pet
or approve either reconstructed mesh for animation.

## Approved reference target

- `canonical-standing.png`: canonical anatomy, face, coat, paws, ears, and age.
- `modeling-turnaround.png`: aligned front, left, rear, and right sculpting views.

Both images were generated for this project from the existing Leo identity and
contain no third-party model asset.

## Reconstruction findings

- `front-reconstruction-qa.png`: good face and front readability, but the unseen
  torso and rear contain single-view surface artifacts.
- `side-reconstruction-qa.png`: materially better torso, legs, tail, and rear,
  but the unseen frontal face lacks the canonical detail.

The QA sheets passed mechanical checks for eight transparent views, clean corner
alpha, and frame safety. They failed the final visual-identity gate and are
reference evidence only. Their accepted regions were consolidated into the
project-owned candidate documented in `../realistic-sculpt-v1/`; the rejected
single-view meshes remain excluded from runtime and source assets.

## Integration status

- Runtime replacement: no
- Rigging approved: no
- Animation transfer approved: no
- Canonical realistic identity approved: yes
