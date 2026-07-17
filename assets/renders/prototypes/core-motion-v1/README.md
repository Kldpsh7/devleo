# Core animation candidate v1

This snapshot freezes the first Phase 2 Waiting, Working, Review, and Failure motion
candidate. It is a visual gate, not runtime-approved art.

- Waiting: 12 frames at 210 ms per frame, looped.
- Working: 16 frames at 145 ms per frame, looped.
- Review: 12 frames at 210 ms per frame, looped.
- Failure: 14 frames at 140 ms per frame, one-shot to a failed hold.
- `*-contact-sheet.png`: complete frame and pose-consistency review.
- `*-preview.gif`: playback at the authored cadence.
- `qa.json`: alpha, timing, safety, registration, and motion validation.
- `visual-qa.txt`: independent visual review result.

Reproduce the complete transparent master frames with
`tools/blender/render_core_animations.sh`; the masters and manifest remain ignored
under `assets/renders/work/`.
