# Blender runtime export

The isolated exporter converts approved 1152×1248 Blender masters directly into
lossless runtime candidates:

```bash
tools/blender/render_idle.sh
tools/blender/render_core_animations.sh
tools/blender/render_locomotion.sh
tools/blender/render_gestures.sh
tools/blender/render_gaze_directions.sh
tools/blender/render_transitions.sh
tools/blender/export_runtime_assets.sh
```

It emits one 8×11 Codex v2 atlas and complete animation-frame families at 1×,
2×, and 4× densities. Each density is resized once from the transparent master;
no tier is enlarged from another tier. Fully transparent RGB is cleared after
resampling.

The fixed atlas rows are Idle, pounce Run right/left, Wave, Jump, Failure,
Waiting, active Working, Review, and the two approved eight-direction gaze rows.
Idle row column 6 contains the required v2 neutral/front cell; column 7 remains
transparent.
The calmer Walk loops and the four seated/roaming transitions remain available
as full-frame families outside the compatibility atlas.

Every family receives one common vertical translation before resize. The lowest
ground-contact frame lands on master line 1214, preserving genuine airborne
motion while keeping stationary and locomotion families on the same desktop
baseline. The result remains a candidate until deterministic atlas QA and final
normal-size visual review pass; this command does not modify installed assets.

The candidate package and QA evidence are generated under the ignored
`assets/renders/work/runtime-export-v1/` directory. The current desktop package
remains unchanged until the custom Blender mode families are complete, the
candidate is reviewed, and the runtime is explicitly switched to it.
