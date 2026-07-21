# Blender gestures v1

This snapshot records Leo's first approved Wave and Jump candidates. It is approved
for later runtime integration but does not replace packaged or installed art.

- Wave: 10-frame seated one-shot at 150 ms/frame. The complete right front-leg
  chain rises, the paw sweeps laterally, and Leo returns exactly to the source pose.
- Jump: 12-frame quadrupedal one-shot at 110 ms/frame. Leo crouches, springs with
  all four paws, remains airborne for eight reviewed frames, lands, and returns
  exactly to the source pose.
- Wave keeps the closed laptop fixed on the floor.
- Jump keeps the closed, constant-size laptop secured at the flank.

`qa.json` records endpoint equality, alpha, safety, registration, uniqueness, and
airborne metrics. Contact sheets, normal-size GIFs, and the background sheet retain
the visual evidence used for approval.

Reproduce the masters and QA with `tools/blender/render_gestures.sh`. Scratch
masters and manifests remain ignored under `assets/renders/work/gestures/`.
