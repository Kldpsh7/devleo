# Graphics Quality Specification

This document is a release gate for all visual assets.

## Visual identity

- The character must read immediately as a young lion: feline muzzle, cub ears, large paws, flexible tail, compact quadrupedal body, and natural joints.
- Avoid upright human posture, human hands, clothing, or human running mechanics.
- Preserve one canonical face, coat palette, markings, eye construction, ear geometry, paw shape, tail shape, and body proportion across every frame.
- The laptop is a thin logo-free silver device. Its dimensions, hinge, keyboard, trackpad, and attachment method remain consistent.
- Fine detail must support the silhouette rather than becoming noise at normal desktop size.

## Source and export requirements

- Master frames: lossless straight-alpha RGBA PNG, sRGB, minimum 1024 x 1024 canvas per frame.
- Runtime tiers: deterministic 1x, 2x, and 4x exports from approved masters.
- No generational resampling: resize once from the approved master for each tier.
- Fully transparent pixels must have cleared hidden RGB.
- Metadata records animation name, frame order, duration, anchor, hitbox, density, and source checksum.
- Runtime art must be reproducible from approved masters and checked-in processing commands.

## Animation budgets

These are initial targets and may increase when motion requires it:

| Animation | Target frames | Loop |
|---|---:|---|
| Idle | 12 | yes |
| Walk left/right | 12 each | yes |
| Run left/right | 12 each | yes |
| Wave | 10 | one-shot then idle |
| Jump | 12 | one-shot then previous state |
| Failure | 14 | one-shot then failed hold/idle |
| Waiting | 12 | yes |
| Active work | 16 | yes |
| Review | 12 | yes |
| Gaze | 16 directions | state-driven |

The window movement rate is independent of sprite FPS. Increasing window update frequency must not duplicate or invent animation frames.

## Motion requirements

### Idle

Subtle breathing, one natural blink, a small tail flick, and a brief curious glance. The feet and body base remain stable.

### Walk and run

Use real quadrupedal gait ordering. Walk is calm and readable; run is a playful cub pounce with a clear airborne phase. Left and right motion must face the direction of travel and have consistent temporal cadence.

### Wave

The cub sits naturally and raises one front paw. No floating marks, lines, text, or detached effects.

### Jump

All four paws participate in the spring. The closed laptop remains secured and never teleports or changes size.

### Failure

The ears flatten before the head lowers. The face-plant is gentle, readable, and physically contacts the closed laptop. Recovery must not snap.

### Waiting

The cub sits with the laptop half-open and tilts its head. This must remain distinct from idle and review.

### Active work

The laptop is fully open. A tail movement taps the trackpad while the front paws remain anatomically plausible. The laptop must not float, detach, or change hinge geometry.

### Review

Squinted eyes, slow trackpad swipe, and alternating ear twitch. The action should read as careful inspection rather than generic typing.

### Gaze

Use 16 clockwise directions. Eyes lead; muzzle and head follow; ears and upper torso provide restrained follow-through; paws and lower body stay registered. Cardinals must read unambiguously as up, screen-right, down, and screen-left.

## Alpha and edge requirements

- No opaque background pixels.
- No matte fringe on light, dark, or saturated backgrounds.
- No accidental transparent bands, interior holes, seams, or scanlines inside the cub or laptop.
- No detached stray pixels or disconnected outline fragments.
- No cropped fur, ears, paws, tail, laptop, or motion extremes.
- No cast floor shadow, glow, aura, motion line, dust, or scenery in runtime sprites.

## Registration requirements

- Stable lower-body anchor and baseline inside each loop.
- No visible scale popping or frame-to-frame resizing.
- Continuous tail and laptop attachment.
- Adjacent gaze directions must not reverse, jump registration, or change identity.
- One-shot animations must begin and end with transitions compatible with their source and destination states.

## Visual QA matrix

Every release candidate must be reviewed:

- At actual display sizes: small, normal, and large.
- At 100%, 150%, and 200% OS scaling.
- On white, black, mid-gray, saturated, and detailed desktop backgrounds.
- In contact sheets and real-time motion previews.
- On macOS Retina, Windows mixed-DPI, Linux X11, and Linux Wayland test environments.

## Deterministic validation

Automated checks must reject:

- Missing or duplicated frames.
- Incorrect dimensions or color mode.
- Empty required frames.
- Nontransparent corners and background regions.
- Pixels touching configured safety edges.
- Alpha holes inconsistent with approved negative space.
- Excessive center, baseline, area, or scale change.
- Missing metadata or checksum mismatch.

Automated metrics are evidence, not a substitute for final normal-size visual review.

## Approval artifacts

Each visual release retains:

- Canonical identity image.
- Animation contact sheet.
- Per-animation preview files.
- Light/dark/busy-background QA sheet.
- Direction QA sheet.
- Deterministic validation JSON.
- Asset manifest with source and export checksums.
- Final visual QA verdict and documented accepted warnings.

