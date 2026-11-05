#!/usr/bin/env bash
# Isolated settings/runtime checks; no live backend or preference writes.
set -euo pipefail
plugin_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
check_dir="$(mktemp -d)"
trap 'rm -rf -- "$check_dir"' EXIT
shell_dir="${OMARCHY_PATH:-/usr/share/omarchy}/shell"
ln -s "$shell_dir/Commons" "$check_dir/Commons"
ln -s "$shell_dir/Ui" "$check_dir/Ui"
cp "$plugin_dir/"{Settings,Appearance,LayoutSettings,ColorPicker,Runtime,Service}.qml "$check_dir/"
cp "$plugin_dir/"{qmldir,layouts.json} "$check_dir/"
cp -r "$plugin_dir/i18n" "$check_dir/"
cat > "$check_dir/shell.qml" <<'QML'
import QtQuick
import Quickshell
ShellRoot {
  Settings { manageBackend: false }
  Settings { manageBackend: false }
  Service { id: service; backendEnabled: false }
  Appearance { id: prefs }
  LayoutSettings { id: chooser; appearance: prefs }
  Timer {
    interval: 700; running: true
    onTriggered: {
      if (chooser.presets.length !== 8) throw new Error("Missing vertical presets")
      service.retrySetup()
      if (!service.rebuildRequested || service.backendCommand().indexOf("--rebuild-observer") < 0) throw new Error("Retry did not request a rebuild")
      if (Runtime.users !== 0 || Runtime.coordinator.backendEnabled) throw new Error("Unexpected startup")
      service.handleZonesdLine('{"event":"setup","state":"building","message":"Building"}')
      if (service.setupState !== "building") throw new Error("No build progress")
      service.handleZonesdLine('{"event":"setup","state":"error","message":"Install headers"}')
      if (service.setupMessage !== "Install headers") throw new Error("Missing error")
      service.handleZonesdLine('{"event":"ready"}')
      if (service.setupState !== "ready") throw new Error("No ready state")
      Runtime.coordinator.ready = false
      var first = Runtime.acquire(), second = Runtime.acquire()
      if (first !== second || Runtime.users !== 2 || !first.backendEnabled) throw new Error("Backend not shared")
      Runtime.release()
      if (!first.backendEnabled) throw new Error("Stopped while another monitor needs it")
      Runtime.release()
      if (first.backendEnabled || Runtime.users !== 0) throw new Error("Last widget did not stop backend")
      console.log("ZONES_SHARED_RUNTIME_AND_SETUP_UI_OK")
      Qt.quit()
    }
  }
}
QML
timeout 15 quickshell -p "$check_dir" --no-duplicate > "$check_dir/check.log" 2>&1
cat "$check_dir/check.log"
rg -q 'ZONES_SHARED_RUNTIME_AND_SETUP_UI_OK' "$check_dir/check.log"
if rg -q 'TypeError|ReferenceError|Unable to assign|Failed to load configuration|Error:' "$check_dir/check.log"; then
    exit 1
fi
