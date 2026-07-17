# Gaze cardinal candidate v2

This snapshot freezes the repaired four-cardinal family after the v1 blind-review
failure. It is a visual gate, not runtime-approved art.

V2 adds camera-compensated head turns and direct whole-iris/pupil surface travel so
the axes remain unmistakable after the 192x208 export.

- `directions/`: full-resolution transparent `000`, `090`, `180`, and `270` masters.
- `gaze-directions.png`: neutral-plus-cardinals review sheet.
- `gaze-preview.gif`: cardinals played at normal pet size.
- `qa.json`: dimensions, alpha, registration, baseline, and uniqueness validation.
- `direction-semantics.json`: independent cardinal landmark review.
- `visual-qa.txt`: independent visual verdict.

Reproduce the masters with `tools/blender/render_gaze_cardinals.sh`; scratch renders
and manifests remain ignored under `assets/renders/work/`.
