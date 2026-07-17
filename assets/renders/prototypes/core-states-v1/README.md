# Core state pose contract v1

This snapshot freezes the Phase 2 pose and laptop-lid contract before animation.
It is a visual gate, not runtime-approved art.

- `states/idle.png`: neutral seated pose with the laptop closed.
- `states/waiting.png`: curious head tilt with the laptop half-open at 48°.
- `states/working.png`: focused pose with the laptop fully open at 96°.
- `states/review.png`: squinted review pose with the laptop fully open at 96°.
- `states/failure.png`: closed-eye, flattened-ear face-plant on the closed lid.
- `state-poses.png`: side-by-side review sheet.
- `qa.json`: state order, lid angles, dimensions, and alpha validation.
- `visual-qa.txt`: independent visual review result.

The complete images are reproduced with `tools/blender/render_state_poses.sh`; scratch
renders and manifests remain ignored under `assets/renders/work/`.
