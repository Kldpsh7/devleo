# Blender locomotion v1

This snapshot records Leo's first approved quadrupedal locomotion family. It is
approved for later runtime integration but does not replace packaged or installed
art.

- `walk-right` and `walk-left`: 12-frame calm four-beat gaits at 125 ms/frame.
- `run-right` and `run-left`: 12-frame playful pounce bounds at 85 ms/frame.
- Walk contact paws compensate for camera projection and hold an 8-pixel master
  baseline drift, about 1.3 pixels at 192x208.
- Each Run contains seven visually reviewed all-paw airborne frames.
- The paw-marked laptop remains closed, constant-size, and secured at the flank.
- Short head/body particle naps prevent emitter-pole silhouette defects.

`qa.json` records alpha, safety, registration, uniqueness, and airborne metrics.
The contact sheets, real-time normal-size GIFs, and background sheet retain the
visual evidence used for approval.

Reproduce the masters and QA with `tools/blender/render_locomotion.sh`. Scratch
masters and manifests remain ignored under `assets/renders/work/locomotion/`.
