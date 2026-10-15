# Validation — 0.4.0 preview

## Environment

Tested on Omarchy Edge, Hyprland 0.56.2 and Quickshell 0.3.2, with an ultrawide
and laptop display at 1.25 scaling. The user confirmed preview alignment,
landing positions and titlebar clearance on both monitors, and is using the
custom color picker.

## Automated coverage

47 Python unit tests cover layout selection and overlaps, monitor/workspace
precedence, strict Floating-mode gating, complete-frame geometry, all four bar
and dock edges, scale/rotation/negative origins, uniform odd and even gaps,
release/resize gesture state, bounded observer parsing, preference persistence,
input validation, build-cache reuse and invalidation, and build failure handling.

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

- Floating workspace mode is required; older Stable releases are unsupported.
- Native compilation depends on the installed Hyprland SDK matching the running
  compositor. An incompatible SDK must be corrected before retrying setup.
- Touchscreen-only dragging and other compositors have not been validated.
- Dock space is reserved conservatively, including for an auto-hiding dock.
- App-specific minimum sizes or unusual decoration overrides may constrain fit.
- GitHub CI runs Python tests and syntax checks; native compilation and shell
  fixtures require the documented Omarchy environment and are checked locally.
