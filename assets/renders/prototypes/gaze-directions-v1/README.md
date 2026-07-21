# Validated 16-direction gaze v1

This snapshot is the first Blender-rendered gaze family to pass the complete Codex
v2 direction gate. It is approved for runtime integration, but has not replaced
the installed or packaged runtime art.

The fixed body and closed laptop remain registered while complete eye surfaces,
head pitch/yaw, ears, and tail follow a continuous 22.5-degree loop. The family
uses the repaired short head-fur nap from cardinal candidate v3.

Validation includes:

- all 16 unique directions at 1152x1248, downscaled once to 192x208;
- zero hidden RGB, zero baseline drift, and bounded center drift;
- loop continuity with no alpha holes or continuity warnings;
- three isolated blind A/B reviews combined by strict majority;
- both cardinal hard gates confirmed;
- independent labeled review of every direction at both scales.

The blind majority found the horizontal cue in `337.5` ambiguous at 192x208. This
is retained as a review warning: the final labeled review confirmed its subtle
up-left landmarks and smooth `315 -> 337.5 -> 000` transition without reversal.

Reproduce the masters and base QA with `tools/blender/render_gaze_directions.sh`.
The Codex hatch-pet direction scripts produce the blind sheet, continuity report,
combined verdict, and validation files stored here.
