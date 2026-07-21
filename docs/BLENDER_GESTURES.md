# Blender gesture contract

Wave and Jump are isolated Blender candidates. They do not replace packaged or
installed runtime art until their visual milestone is approved.

## Wave

- 10-frame one-shot at 150 ms/frame.
- Leo stays in a natural seated pose and raises one complete front-leg chain.
- The paw swings twice, then returns exactly to the source pose.
- The closed laptop remains fixed in front of the seated cub.

## Jump

- 12-frame one-shot at 110 ms/frame.
- A quadrupedal crouch leads into a four-paw spring, airborne tuck/stretch, landing,
  and exact return to the source pose.
- The closed laptop stays constant-size and secured against Leo's flank.
- The sequence is an in-place gesture; window movement remains independent.

Generate both candidates with:

```bash
tools/blender/render_gestures.sh
```

QA records endpoint equality, alpha, safety margins, baseline/center travel, unique
motion frames, Jump airborne frames, normal-size previews, and background checks.
