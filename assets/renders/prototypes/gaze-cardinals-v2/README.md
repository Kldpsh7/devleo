# Gaze cardinal candidate v2

This snapshot freezes the second four-cardinal family after the v1 blind-review
failure. It was superseded by v3 after two of three fresh blind reviewers still
classified both cardinal axes as ambiguous. It must not be used for runtime art.

V2 added camera-compensated head turns and direct whole-iris/pupil surface travel,
but the isolated A/B test showed that the result was still insufficient.

- `directions/`: full-resolution transparent `000`, `090`, `180`, and `270` masters.
- `gaze-directions.png`: neutral-plus-cardinals review sheet.
- `gaze-preview.gif`: cardinals played at normal pet size.
- `qa.json`: dimensions, alpha, registration, baseline, and uniqueness validation.
- `direction-semantics.json`: independent cardinal landmark review.
- `visual-qa.txt`: independent visual verdict.

Reproduce the masters with `tools/blender/render_gaze_cardinals.sh`; scratch renders
and manifests remain ignored under `assets/renders/work/`.
