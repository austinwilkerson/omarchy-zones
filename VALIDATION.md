# Floating Snap Zones — validation for 0.4.4 preview

## Current verified environment

Omarchy **RC Channel**, package 4.5.0-1, Hyprland 0.56.2 and Quickshell 0.3.2.
See the RC compatibility and setup recovery section for the November 4 checks.

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
synchronization, preference persistence, all six layout choices, workspace
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
