# Blender Idle prototype v1

This is the first Blender pipeline approval artifact, not runtime-approved art.

- `neutral.png`: full-resolution transparent reference render.
- `contact-sheet.png`: all twelve Idle frames.
- `background-qa.png`: transparent-edge review on four backgrounds.
- `idle-preview.gif`: slow six-FPS loop preview.
- `qa.json`: deterministic alpha, dimensions, edge, and registration measurements.
- `visual-qa.txt`: independent visual review result.

The complete lossless frame sequence is reproducible from `assets/source-3d/leo.blend`
with `tools/blender/render_idle.sh`; scratch masters remain ignored under
`assets/renders/work/`.
