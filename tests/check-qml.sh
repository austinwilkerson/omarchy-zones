#!/usr/bin/env bash
# Isolated settings/runtime checks using a fake runner.
set -euo pipefail
plugin_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
check_dir="$(mktemp -d)"
trap 'rm -rf -- "$check_dir"' EXIT
shell_dir="${OMARCHY_PATH:-/usr/share/omarchy}/shell"
ln -s "$shell_dir/Commons" "$check_dir/Commons"
ln -s "$shell_dir/Ui" "$check_dir/Ui"
cp "$plugin_dir/"{Settings,Appearance,LayoutSettings,ColorPicker,Runtime,Service}.qml "$check_dir/"
cp "$plugin_dir/"{qmldir,layouts.json,settings.py} "$check_dir/"
cp -r "$plugin_dir/i18n" "$check_dir/"
cat > "$check_dir/runner.py" <<'PY'
import json
from pathlib import Path
import sys
import time

count_file = Path(__file__).with_name("attempts")
attempt = int(count_file.read_text()) + 1 if count_file.exists() else 1
count_file.write_text(str(attempt))
assert ("--rebuild-observer" in sys.argv) == (attempt == 2)
if attempt == 1:
    print(json.dumps({"event": "setup", "state": "error", "message": "Install headers"}), flush=True)
    sys.exit(78)
print(json.dumps({"event": "ready"}), flush=True)
if attempt == 2:
    print(json.dumps({"event": "preview", "zone": "fixture", "rect": {"w": 20, "h": 20}}), flush=True)
if attempt == 3:
    time.sleep(.2)
    sys.exit(1)
time.sleep(30)
PY
cat > "$check_dir/shell.qml" <<'QML'
import QtQuick
import Quickshell
ShellRoot {
  Settings { manageBackend: false; manageIpc: false }
  Settings { manageBackend: false; manageIpc: false }
  Service { id: service; backendEnabled: false }
  Appearance {
    id: prefs
    configPath: decodeURIComponent(String(Qt.resolvedUrl("preferences.json")).replace(/^file:\/\//, ""))
  }
  LayoutSettings { id: chooser; appearance: prefs }
  Timer {
    interval: 700; running: true
    onTriggered: {
      if (chooser.presets.length !== 8) throw new Error("Missing vertical presets")
      if (Runtime.users !== 0 || Runtime.coordinator.backendEnabled) throw new Error("Unexpected startup")
      Runtime.coordinator.initialized = false
      var first = Runtime.acquire(), second = Runtime.acquire()
      if (first !== second || Runtime.users !== 2 || !first.backendEnabled) throw new Error("Backend not shared")
      Runtime.release()
      if (!first.backendEnabled) throw new Error("Stopped while another monitor needs it")
      Runtime.release()
      if (first.backendEnabled || Runtime.users !== 0) throw new Error("Last widget did not stop backend")
      console.log("ZONES_SHARED_RUNTIME_AND_SETUP_UI_OK")
      prefs.save({gap_px: 12})
      prefs.load()
      if (prefs.gap !== 12) throw new Error("Reload replaced an unsaved setting")
      verifyPrefs.start()
      service.backendEnabled = true
      verifyWorker.start()
    }
  }
  Timer {
    id: verifyWorker
    property int step: 0
    interval: 50; repeat: true
    onTriggered: {
      if (step === 0 && service.backendPhase === "failed") {
        if (service.setupMessage !== "Install headers") throw new Error("Setup error was lost")
        service.retrySetup()
        if (!service.rebuildRequested || service.backendCommand().indexOf("--rebuild-observer") < 0)
          throw new Error("Retry did not request a rebuild")
        step++
      } else if (step === 1 && service.previewVisible) {
        if (service.setupState !== "ready") throw new Error("No ready state")
        service.backendEnabled = false
        service.handleZonesdLine('{"event":"ready"}')
        service.handleZonesdLine('{"event":"preview","zone":"stale","rect":{"w":20,"h":20}}')
        if (service.previewVisible || service.previewZone || service.setupState === "ready")
          throw new Error("Stopping worker published stale output")
        service.backendEnabled = true
        if (service.backendPhase !== "stopping") throw new Error("Re-enabled before old worker exited")
        step++
      } else if (step === 2 && service.backendPhase === "running") {
        step++
      } else if (step === 3 && service.backendPhase === "backoff") {
        if (service.setupState === "ready" || service.previewVisible)
          throw new Error("Exited worker still appeared ready")
        step++
      } else if (step === 4 && service.backendPhase === "running") {
        service.backendEnabled = false
        step++
      } else if (step === 5 && service.backendPhase === "idle") {
        console.log("ZONES_WORKER_LIFECYCLE_OK")
        Qt.quit()
      }
    }
  }
  Timer {
    id: verifyPrefs
    property int step: 0
    interval: 500
    repeat: true
    onTriggered: {
      if (step === 0) {
        if (prefs.gap !== 12 || prefs.error) throw new Error("Initial save failed")
        prefs.save({gap_px: -1})
      } else if (step === 1) {
        if (prefs.gap !== 12 || !prefs.error) throw new Error("Failed write did not restore saved preferences and retain its error")
        prefs.save({gap_px: 16})
      } else {
        if (prefs.gap !== 16 || prefs.error) throw new Error("Successful retry did not clear save error")
        console.log("ZONES_PREFERENCE_WRITE_ORDERING_OK")
        stop()
      }
      step++
    }
  }
}
QML
timeout 15 quickshell -p "$check_dir" --no-duplicate > "$check_dir/check.log" 2>&1 || { cat "$check_dir/check.log"; exit 1; }
cat "$check_dir/check.log"
rg -q 'ZONES_SHARED_RUNTIME_AND_SETUP_UI_OK' "$check_dir/check.log"
rg -q 'ZONES_WORKER_LIFECYCLE_OK' "$check_dir/check.log"
rg -q 'ZONES_PREFERENCE_WRITE_ORDERING_OK' "$check_dir/check.log"
if rg -q 'TypeError|ReferenceError|Unable to assign|Failed to load configuration|Error:' "$check_dir/check.log"; then
    exit 1
fi
