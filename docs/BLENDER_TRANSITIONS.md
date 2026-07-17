# Blender locomotion transitions

These isolated candidates connect canonical seated Idle to the approved first
Walk pose without changing packaged runtime art.

```bash
tools/blender/render_transitions.sh
```

The command renders 20-frame, 70 ms/frame departures in both directions. Each
return-to-Idle sequence is the exact pixel-reversed departure, so roaming can
stop without a pose or laptop snap. Leo crouches, turns onto four paws, and lifts
the closed laptop outward from its floor position with a following paw before
settling it into the approved flank carry.

Before QA, a deterministic registration pass shifts every non-airborne frame so
the lowest visible pixel lands on master ground line 1214. This keeps Leo's paws
fixed to the desktop baseline even though the seated and quadrupedal silhouettes
have different heights.

Deterministic QA verifies transparent masters, cleared hidden RGB, safe margins,
unique frames, bounded adjacent center/baseline/area changes, a shared Idle
endpoint, and exact forward/reverse pairs. Contact sheets, actual-size GIFs, and
light/dark/saturated background evidence are generated beside the frames.
