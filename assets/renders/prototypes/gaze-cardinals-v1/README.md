# Gaze cardinal candidate v1

This snapshot records the first labeled cardinal review. It was superseded by v2
after three blind reviewers found every normal-size A/B direction pair ambiguous.
It must not be used for runtime art.

- `directions/`: full-resolution transparent `000`, `090`, `180`, and `270` masters.
- `gaze-directions.png`: neutral-plus-cardinals review sheet.
- `gaze-preview.gif`: cardinals played at normal pet size.
- `qa.json`: dimensions, alpha, registration, baseline, and uniqueness validation.
- `direction-semantics.json`: independent cardinal landmark review.
- `visual-qa.txt`: independent visual verdict.

Reproduce the masters with `tools/blender/render_gaze_cardinals.sh`; scratch renders
and manifests remain ignored under `assets/renders/work/`.
