# Architecture

## Runtime components

The application is one user-level GUI process plus a CLI client.

1. `overlay`: owns the transparent frameless window, sprite rendering, hit testing, dragging, and screen geometry.
2. `animation`: selects animation states, advances frames, and handles temporary overrides.
3. `movement`: plans safe destinations, walks or runs between them, snaps to anchors, and respects screen boundaries.
4. `platform`: provides autostart, application-menu registration, notification-area integration, and OS-specific window behavior.
5. `ipc`: guarantees a single GUI instance and routes CLI commands to it.
6. `config`: validates and persists user settings atomically.
7. `assets`: loads versioned pet manifests and chooses the correct density tier.

## State priority

Highest priority wins:

1. Shutdown or uninstall.
2. Active drag.
3. Explicit animation or position override.
4. Hidden or paused.
5. Anchored or stay mode.
6. External local event state: failure, waiting, review, or working.
7. Autonomous roaming.
8. Idle.

Temporary states must have explicit completion and recovery transitions. The pet must never remain stuck in a one-shot jump, failure, or wave animation.

## Rendering model

- Movement updates target 60 Hz where the compositor permits it.
- Sprite animation uses animation-specific FPS independent of window movement.
- Runtime selects 1x, 2x, or 4x assets from display scale and configured pet size.
- The transparent window bounds follow the visible sprite plus a small interaction margin.
- Transparent regions should not block clicks when the platform supports reliable dynamic hit testing.

## Positioning

Positions are stored in logical screen coordinates with a screen identifier and a normalized fallback. On display removal or resolution change, the pet is clamped into the nearest usable work area.

Dragging pauses autonomous movement. Dropping inside a configurable corner snap zone creates an anchor. Dropping elsewhere leaves the pet in `stay` mode until roaming is explicitly resumed.

## Local IPC

The first process becomes the GUI server. Later invocations send a versioned JSON command over a user-scoped local socket or named pipe and exit.

- macOS/Linux: Unix domain socket under the user runtime directory.
- Windows: user-scoped named pipe.
- Authentication: current-user filesystem or pipe permissions; no TCP listener.

## Configuration

Configuration is versioned and stored under platform-standard user config paths. Writes use a temporary file plus atomic replacement. Invalid values are rejected without modifying the last valid configuration.

## Platform adapters

- macOS: Qt window flags plus Cocoa floating-level/all-Spaces policy, native application icon, and LaunchAgent autostart.
- Windows: Qt tool window, Startup entry, application shortcut, named-pipe IPC.
- Linux: XDG application/autostart entries, compositor detection, Unix-socket IPC.

Linux window behavior must be feature-detected. X11 behavior must not be assumed to work identically under Wayland.

## External state integration

The core application does not inspect screens, keystrokes, clipboard contents, or private application data. Optional integrations communicate through a documented local event command or socket API.

Example:

```bash
lion-cub-pet event working --source editor --ttl 30
lion-cub-pet event waiting --source agent
lion-cub-pet event clear --source agent
```

Sources are namespaced and have explicit TTL or clear semantics so stale integrations cannot leave the pet in the wrong state.
