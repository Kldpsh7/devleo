# Gaze cardinal candidate v1

This snapshot freezes the four approved cardinal pose families before interpolating
the complete 16-direction gaze loop. It is a visual gate, not runtime-approved art.

- `directions/`: full-resolution transparent `000`, `090`, `180`, and `270` masters.
- `gaze-directions.png`: neutral-plus-cardinals review sheet.
- `gaze-preview.gif`: cardinals played at normal pet size.
- `qa.json`: dimensions, alpha, registration, baseline, and uniqueness validation.
- `direction-semantics.json`: independent cardinal landmark review.
- `visual-qa.txt`: independent visual verdict.

Reproduce the masters with `tools/blender/render_gaze_cardinals.sh`; scratch renders
and manifests remain ignored under `assets/renders/work/`.
