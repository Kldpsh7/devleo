# Blender gaze mechanics

Leo's gaze is a continuous clockwise 16-pose family. The eyes lead, the complete
head and muzzle follow, and the ears add restrained follow-through. The torso,
paws, tail base, closed laptop, canvas registration, scale, and lower baseline stay
fixed. The laptop never rotates with the gaze.

## Cardinal pose families

- `000 up`: irises and pupils rise inside both eye apertures; the muzzle and head
  pitch upward; ears lift slightly. More chin is visible while the laptop stays fixed.
- `090 screen-right`: irises, pupils, nose, and muzzle turn toward the viewer's
  right edge. Leo's screen-right cheek becomes more prominent and the opposite ear
  follows without changing the seated silhouette.
- `180 down`: irises and pupils lower; the muzzle and head pitch toward the laptop;
  ears settle outward. The cub remains seated rather than entering Working.
- `270 screen-left`: irises, pupils, nose, and muzzle turn toward the viewer's left
  edge. It visibly opposes `090` while preserving identity and laptop placement.

## Motion budget

Each 22.5° step receives one-sixteenth of a periodic eye/head/ear arc. Eye travel is
limited to the existing aperture. The renderer compensates for the fixed camera's
19.7° three-quarter yaw, then permits 46° of screen-axis yaw and 32° of pitch so the
cardinals remain readable after the 192x208 export. Ear follow-through peaks at 3°.
No adjacent pair may introduce a new prop, expression, scale, baseline, or
whole-sprite tilt. `337.5 -> 000` and `157.5 -> 180` use the same step size as every
other boundary.
