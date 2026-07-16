# Leo the Dev — Lion Cub Pet

A playful, high-quality desktop lion cub that walks and runs across the screen, reacts to work states, can be dragged and anchored, and uses a logo-free silver laptop as part of its animation language.

The product is intended to run as a transparent GUI overlay on macOS, Windows, and Linux while being installed and controlled from the terminal.

> Status: active pre-release implementation. The PySide6 overlay, local CLI control, roaming, dragging, anchoring, shared tray/right-click controls, comic dialogue bubbles, custom modes, configuration, user-level autostart, and validated animation art are implemented.

## Product goals

- Look like a real lion cub rather than a humanoid mascot.
- Use expressive animal motion: quadrupedal walking, playful pouncing, ear movement, tail movement, head tilts, and paw interaction.
- Render cleanly on light, dark, detailed, standard-DPI, and high-DPI desktops.
- Run as a frameless transparent overlay without stealing focus.
- Roam safely inside the current screen's usable work area.
- Allow direct dragging and persistent placement.
- Stop roaming when anchored, including a dedicated bottom-right anchor.
- Expose every behavior through a documented CLI and system-tray menu.
- Install from a GitHub repository without requiring a native DMG, MSI, or DEB installer.
- Collect no telemetry by default.

## Character specification

The pet is a playful lion cub with realistic feline proportions, four-paw locomotion, rounded cub features, expressive ears, a flexible tail, and no human clothing or human posture.

Its display name is **Leo the Dev**. The package and terminal command remain `lion-cub-pet` for compatibility.

Its equipment is a thin, logo-free silver laptop inspired by a MacBook. The laptop remains physically attached or carried while the cub moves and is placed on the ground for work animations.

### Required animation behavior

| State | Required visual behavior |
|---|---|
| Idle | Breathing, blink, tiny tail flick, brief curious glance |
| Walk | Natural quadrupedal cub walk with alternating paws |
| Run | Playful pounce-like gait, never human running |
| Wave | Cub sits and raises one front paw without detached motion marks |
| Jump | Four-paw spring with the closed laptop secured against its side |
| Failure | Ears flatten and the cub gently face-plants onto the closed laptop |
| Waiting | Cub sits, tilts its head, and keeps the laptop half-open |
| Active work | Laptop fully open; tail taps the trackpad while paws interact naturally |
| Review | Squinted eyes, slow trackpad swipe, alternating ear twitch |
| Gaze | Eyes, head, ears, muzzle, and upper body follow 16 clockwise directions |

Stationary seated states render at 85% of the selected movement size so the cub remains visually consistent with the running gait.

### Personality modes

| Mode | Visual behavior |
|---|---|
| Normal | Roaming, working, waiting, review, and failure state machine |
| Relax | 8-frame sunglasses-and-cola lounge loop at 260 ms/frame |
| Focus | 8-frame headband, folded sitting, and laptop loop at 210 ms/frame |
| Sleep | 8-frame curled breathing loop at 360 ms/frame |
| Motivate | 8-frame encouraging gesture at 240 ms/frame; returns to Normal after 5–8 seconds |

Leo uses shuffled dialogue bags, so a line does not repeat until the current state’s alternatives have been used. Advice appears at a low random frequency and temporarily uses a smooth 8-frame water-offering animation at 280 ms/frame.

Laptop state is part of the animation contract:

- Closed while walking, running, jumping, or waving.
- Half-open while waiting for input.
- Fully open during active work and review.
- Closed and physically contacted during the failure reaction.

## Interaction model

- `Roaming`: the cub chooses a safe destination, walks or runs toward it, idles, then continues.
- `Staying`: the cub remains at its current position but continues its idle animation.
- `Anchored`: the cub remains attached to a selected screen corner.
- `Dragging`: dragging immediately pauses autonomous movement; the final position is persisted.
- `Bottom-right`: dragging into the bottom-right snap zone anchors the cub there.
- `Hidden`: the overlay is not rendered, but configuration remains available.
- `Paused`: animation and autonomous movement stop without exiting the process.

The default `full-screen` bounds let visible pet pixels reach all four physical screen corners. Use `bounds work-area` to keep it outside the taskbar or Dock area.

## Installation design

The planned installation path uses `uv` to install the Python package from GitHub. This avoids distributing a downloaded native application bundle while still creating a GUI application entry and optional launch-at-login integration.

```bash
# macOS and Linux
uv tool install "git+https://github.com/<OWNER>/lion-cub-pet"
lion-cub-pet install --autostart --start
```

```powershell
# Windows PowerShell
uv tool install "git+https://github.com/<OWNER>/lion-cub-pet"
lion-cub-pet install --autostart --start
```

The installer will create only user-level files by default. System-wide installation will not be required.

## CLI contract

The executable name is `lion-cub-pet`. All mutating commands should support `--json` where automation needs structured output.

### Lifecycle

```bash
lion-cub-pet install [--autostart] [--start]
lion-cub-pet uninstall [--keep-config] [--keep-assets]
lion-cub-pet start
lion-cub-pet stop
lion-cub-pet restart
lion-cub-pet status [--json]
lion-cub-pet version
```

### Visibility and process state

```bash
lion-cub-pet show
lion-cub-pet hide
lion-cub-pet toggle
lion-cub-pet pause
lion-cub-pet resume
lion-cub-pet quit
```

### Movement and placement

```bash
lion-cub-pet roam
lion-cub-pet stay
lion-cub-pet anchor current
lion-cub-pet anchor bottom-right
lion-cub-pet anchor bottom-left
lion-cub-pet anchor top-right
lion-cub-pet anchor top-left
lion-cub-pet unanchor
lion-cub-pet move <x> <y>
lion-cub-pet screen <index>
lion-cub-pet screen next
lion-cub-pet speed slow
lion-cub-pet speed normal
lion-cub-pet speed fast
lion-cub-pet speed <pixels-per-second>
```

### Appearance

```bash
lion-cub-pet size small
lion-cub-pet size normal
lion-cub-pet size large
lion-cub-pet size <scale>  # clamped to 0.70-1.25
lion-cub-pet opacity <0.25-1.0>
lion-cub-pet always-on-top on|off
lion-cub-pet click-through on|off
```

### Behavior

```bash
lion-cub-pet personality playful
lion-cub-pet mode normal|relax|focus|sleep|motivate
lion-cub-pet dialogues on|off
lion-cub-pet advice on|off
lion-cub-pet advice-now
lion-cub-pet say <text>
lion-cub-pet bounds work-area|full-screen
lion-cub-pet idle-delay <seconds>
lion-cub-pet run-chance <0-100>
lion-cub-pet snap-distance <pixels>
lion-cub-pet avoid-cursor on|off
```

### Animation controls and QA

```bash
lion-cub-pet play idle
lion-cub-pet play walk
lion-cub-pet play run
lion-cub-pet play wave
lion-cub-pet play jump
lion-cub-pet play failure
lion-cub-pet play waiting
lion-cub-pet play working
lion-cub-pet play review
lion-cub-pet look <0-359>
lion-cub-pet laptop auto|closed|half-open|open
lion-cub-pet demo
lion-cub-pet preview <animation>
```

`play`, `look`, `laptop`, `demo`, and `preview` are explicit overrides intended for testing and demonstrations. `lion-cub-pet play auto` returns control to the state machine.

### Launch at login

```bash
lion-cub-pet autostart enable
lion-cub-pet autostart disable
lion-cub-pet autostart status
```

### Configuration

```bash
lion-cub-pet config list
lion-cub-pet config get <key>
lion-cub-pet config set <key> <value>
lion-cub-pet config unset <key>
lion-cub-pet config reset
lion-cub-pet config path
lion-cub-pet config edit
```

### Diagnostics and maintenance

```bash
lion-cub-pet doctor
lion-cub-pet logs
lion-cub-pet logs --follow
lion-cub-pet paths
lion-cub-pet check-update
lion-cub-pet update
lion-cub-pet completion bash
lion-cub-pet completion zsh
lion-cub-pet completion fish
lion-cub-pet completion powershell
```

## System-tray and right-click controls

The same menu is available from the system tray and by right-clicking Leo:

- Show or hide pet.
- Roam, stay, or anchor bottom-right.
- Pause or resume.
- Select normal, relax, focus, sleep, or motivate mode.
- Select a constrained small, normal, or large size.
- Request an advice animation or sample dialogue.
- Quit.

## Technical direction

- Python 3.11 or newer.
- PySide6/Qt for the transparent cross-platform overlay.
- `uv` for dependency management, tool installation, and builds.
- Pillow for deterministic sprite validation and asset processing.
- Typer or Click for the CLI.
- Platform-specific adapters only for autostart, application-menu integration, and compositor differences.
- A single animation state machine shared by all operating systems.
- Local IPC so CLI commands control the running GUI process without spawning duplicates.

See [Architecture](docs/ARCHITECTURE.md) and [Graphics quality](docs/GRAPHICS_QUALITY.md).

## Repository layout

```text
lion-cub-pet/
├── assets/
│   ├── README.md
│   ├── source/          # original high-resolution working art
│   ├── approved/        # reviewed master frames and metadata
│   └── runtime/         # deterministic runtime exports
├── docs/
│   ├── ARCHITECTURE.md
│   └── GRAPHICS_QUALITY.md
├── src/lion_cub_pet/
│   ├── cli/
│   ├── overlay/
│   ├── animation/
│   ├── movement/
│   ├── platform/
│   └── assets/
├── tests/
├── scripts/
├── pyproject.toml
└── README.md
```

## Development commands

For local development without `uv`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/lion-cub-pet install --start
```

Windows uses `.venv\Scripts\lion-cub-pet.exe`.

Project checks:

```bash
uv sync --all-groups
uv run lion-cub-pet --help
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

## Graphics quality policy

High visual quality is a release gate, not optional polish.

- Master frames must be lossless RGBA PNG at a minimum 1024 x 1024 canvas per frame.
- Runtime exports must include density-appropriate 1x, 2x, and 4x tiers.
- The cub's face, proportions, coat markings, eye construction, laptop geometry, and color palette must remain consistent across every frame.
- No cropped ears, paws, tail, laptop, or motion extremes.
- No color fringe, matte halo, accidental transparent body holes, detached effects, or frame seams.
- Animation registration must prevent size popping, baseline jumps, and prop teleportation.
- Every animation must be reviewed at actual display size on light, dark, and visually busy backgrounds.
- QA must cover 100%, 150%, and 200% display scaling.
- Source art and runtime exports must remain reproducible through checked-in metadata and scripts.

The complete acceptance criteria are in [Graphics quality](docs/GRAPHICS_QUALITY.md).

## Cross-platform requirements

### macOS

- Transparent native floating-level overlay across Spaces and full-screen apps.
- Lion-cub application and tray icons instead of the Python launcher icon.
- User-level LaunchAgent for optional autostart.
- Correct behavior across Spaces and multiple displays.
- Retina asset selection.

### Windows

- Transparent tool window with no taskbar button while the pet is active.
- User-level Startup integration.
- Correct behavior across mixed-DPI displays and taskbar placements.

### Linux

- X11 and Wayland detection.
- User-level `.desktop` entry and XDG autostart entry.
- Document compositor-specific limitations instead of silently failing.
- Test at least GNOME and KDE on both supported display paths where practical.

## Privacy and security

- No telemetry by default.
- No screen capture, keyboard logging, clipboard access, or file indexing.
- No elevated privileges for normal installation.
- Network access limited to an explicit update check.
- Release artifacts accompanied by SHA-256 checksums.
- Configuration parsed as data and never executed as shell code.
- Logs must not contain usernames, tokens, environment variables, or unrelated file paths.

## Testing strategy

- Unit tests for animation state selection, movement boundaries, anchoring, and configuration.
- Golden-image tests for asset dimensions, alpha, registration, and expected frame counts.
- IPC tests proving one GUI process and reliable CLI control.
- Cross-platform smoke tests for start, stop, drag, roam, anchor, autostart, and uninstall.
- Long-running soak test for CPU use, memory stability, display changes, and sleep/wake recovery.
- Visual QA sheets and motion previews for every animation release.

## Release plan

1. Implement the CLI, configuration model, and single-instance IPC.
2. Implement a placeholder overlay and cross-platform movement engine.
3. Produce and approve the final high-resolution lion cub identity.
4. Generate, validate, and integrate every animation.
5. Add autostart and application-menu integration per platform.
6. Add test automation and visual QA artifacts.
7. Publish versioned GitHub releases and the terminal installation instructions.

## Additional product features worth including

- Multi-monitor awareness and per-screen anchoring.
- Reduced-motion mode and animation-rate control.
- Battery-saver mode that lowers animation FPS while unplugged.
- Do-not-disturb schedule.
- Per-application exclusion list for games, presentations, or screen sharing.
- Importable pet packs with a versioned manifest.
- Accessibility option to disable pointer avoidance and motion.
- Crash-safe restoration of the last valid position and state.
- A scripted demo mode for release videos and screenshots.
- Optional local event API so editors or agents can request `working`, `waiting`, `review`, or `failure` without screen inspection.

## Licensing

No license has been selected yet. Before public distribution, choose licenses separately for:

- Source code.
- Original lion cub artwork and animation assets.
- Third-party libraries, fonts, and bundled resources.

Do not assume the code license automatically grants redistribution rights for the artwork.
