# Floating Snap Zones validation

## Current verified environment

Omarchy **Stable**, package 4.5.0-3, Hyprland 0.56.2 and Quickshell 0.3.2.
Earlier RC and Edge results are retained below.

## Runtime state audit

| Workflow | Owner | States and transition rules |
| --- | --- | --- |
| Shared backend ownership | [Runtime.qml](Runtime.qml) | The first widget starts the coordinator. Additional widgets share it. The last widget requests shutdown. |
| Worker and setup | [Service.qml](Service.qml), [runner.py](runner.py) | Idle → starting → running. Observer failure can leave the worker degraded. Shutdown ignores late output and waits for exit before replacement. Unexpected exit enters backoff. Setup exit 78 enters failed until Retry or a fresh enable. Explicit Retry forces a rebuild. |
| Native observer and cache | [runner.py](runner.py), [zones/observer.py](zones/observer.py) | Check the versioned cache or build into it. Connect, validate pointer frames and unload on exit when this process owns the helper. |
| Window drag and landing | [zones/drag.py](zones/drag.py), [zonesd.py](zonesd.py) | Distinguish drag from resize and cancel when the window changes. Preview an eligible Floating target while held. Recheck on release, snap once and clear the preview. Per-window guards track movement and size reconciliation. |
| Overlay | [Service.qml](Service.qml) | A running worker can publish a preview on one output. Clear, stop, exit or observer failure resets the whole preview. |
| Layout scope and inheritance | [LayoutSettings.qml](LayoutSettings.qml), [Appearance.qml](Appearance.qml) | Monitor/workspace selection edits one scope. Workspace-specific settings take precedence. Clearing an override restores inheritance. |
| Appearance and persistence | [Settings.qml](Settings.qml), [ColorPicker.qml](ColorPicker.qml), [Appearance.qml](Appearance.qml), [settings.py](settings.py) | Theme or custom color feeds the preview. Edits apply immediately in the panel, queue, then persist atomically. Reload waits for outstanding edits. A failed write reconciles with disk and retains its error until a successful save. |

`bash tests/check-qml.sh` exercises setup failure, explicit Retry, late output
during shutdown, re-enabling before exit, automatic restart after a crash, and
preference write failure and recovery in temporary storage.

## Earlier integration environment

The original checks used Omarchy Edge, Hyprland 0.56.2 and Quickshell 0.3.2,
with an ultrawide and laptop display at 1.25 scaling. The user confirmed preview alignment,
landing positions and titlebar clearance on both monitors, and is using the
custom color picker.

## Automated coverage

52 Python unit tests cover layout selection and overlaps, monitor/workspace
precedence, strict Floating-mode gating, complete-frame geometry, all four bar
and dock edges, scale/rotation/negative origins, uniform odd and even gaps,
release/resize gesture state, bounded observer parsing, preference persistence,
stacked horizontal-row layouts, input validation, build-cache reuse and invalidation, and build failure handling.

Separate Quickshell fixtures verify theme and custom color bindings, picker
synchronization, preference persistence, all eight layout choices, workspace
inheritance, shared coordinator references and setup progress/error states.
These fixtures do not start a backend against the parent desktop.

A fresh cache build compiles the native observer from source and starts the
backend in dry-run mode. A repeat invocation reuses the binary. The installed
widget also built into the real user cache automatically. Enable/disable checks
confirmed one backend across two monitors, helper unload on disable and cached
startup on re-enable. Existing preferences were preserved.

## Compositor integration

A disposable nested Hyprland was used for actual window placements with top,
right, bottom and left bars at scales 1 and 1.25. Five placements per case matched
the intended decorated frame. Real titlebar drag tests confirmed no snapping
while held and snapping on release. Earlier runs also verified manual resizing
and suppression in saved Tiling mode.

The synthetic border-resize gesture did not actually resize its target on two
later attempts, so those attempts were inconclusive for resize integration.
Resize cancellation remains covered by unit tests; no universal gesture or
hardware compatibility claim is made.

## Limits

- Floating workspace mode is required; releases without that capability are unsupported.
- Native compilation depends on the installed Hyprland SDK matching the running
  compositor. An incompatible SDK must be corrected before retrying setup.
- Touchscreen-only dragging and other compositors have not been validated.
- Dock space is reserved conservatively, including for an auto-hiding dock.
- App-specific minimum sizes or unusual decoration overrides may constrain fit.
- GitHub CI runs Python tests and syntax checks; native compilation and shell
  fixtures require the documented Omarchy environment and are checked locally.

## Additional user confirmation

The user reported that version 0.4.0 loaded and worked on a second machine,
a 5090 desktop. Its exact Omarchy/Hyprland versions were not independently
checked, and the new vertical presets have not yet been confirmed on that
machine.


## RC compatibility and setup recovery

Verified on 2026-11-04 with Omarchy channel `rc`, package `4.5.0-1`, Hyprland
0.56.2 and Quickshell 0.3.2. The installed observer is loaded and successful
zone snaps appear in the current shell log. The isolated QML fixture passes
panel loading, shared-runtime lifecycle, setup states and Retry's rebuild flag.

New runner tests verify explicit rebuild routing, replacement and reuse of a
cached helper, failed-force invalidation and subsequent recovery. A real SDK
build in an isolated cache is deliberately replaced with invalid bytes; Retry's
CLI rebuild path produces a new ELF shared object without touching an unrelated
cache slot. These checks do not move windows or load the test helper into the
parent compositor.


## Display-name migration

Renamed from Omarchy Zones to Floating Snap Zones. The plugin ID
`io.github.austinwilkerson.zones`, repository URL, runtime namespace and settings
paths remain unchanged. Source-provided native helper descriptions use the new
name while its lookup name stays compatible with existing installations.

## Stable 4.5 compatibility

Verified on 2026-11-05 with channel `stable`, package `4.5.0-3`, Hyprland
0.56.2 and Quickshell 0.3.2. All 52 Python tests pass. The repeatable
`bash tests/check-qml.sh` fixture loads settings, checks all eight presets,
setup progress/errors, forced Retry routing and shared coordinator lifecycle
without starting a desktop backend or writing preferences.

The native observer compiles against the installed Stable SDK in an isolated
cache; a second invocation reuses the same shared object. The installed
observer remains loaded. Its native code and 0.4.4 helper version are unchanged
in this 0.4.5 documentation/test update; the existing ABI-specific cache remains
valid. The earlier nested drag/placement results above were not repeated on
Stable and remain separately scoped.
