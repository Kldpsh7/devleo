# Blender locomotion contract

Leo's locomotion is a separate Blender candidate and does not replace runtime art
until visual approval.

## Animation contract

- Walk right/left: 12-frame four-beat quadrupedal gait, 125 ms per frame.
- Run right/left: 12-frame playful bounding pounce, 85 ms per frame.
- The window translation rate remains independent of animation timing.
- The head, muzzle, paws, ears, tail, and cub proportions remain canonical.
- The laptop is closed, held at a constant scale, and carried against the near flank.
- The walk keeps at least one supporting paw near the baseline.
- The run contains a readable all-paw airborne phase.
- Left and right face the direction of travel and use identical timing.
- Contact paws compensate for the orthographic camera's ground-plane projection so
  the Walk baseline does not bob as paws advance and recede in depth.
- A consistent short particle nap keeps the profile silhouette clean across the
  head, torso, chest, and haunch emitters.

Generate the candidate with:

```bash
tools/blender/render_locomotion.sh
```

The command renders transparent 1152x1248 masters, clears hidden RGB, validates
registration and airborne frames, and emits normal-size contact sheets and GIFs.
