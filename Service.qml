import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons as Commons

// Headless coordinator: keeps zonesd.py alive (snap on) and paints a
// themed, click-through zone preview while a floating window is dragged.
Item {
  id: root
  property var shell: null
  property bool backendEnabled: true

  readonly property string pluginDir: decodeURIComponent(String(Qt.resolvedUrl(".")).replace(/^file:\/\//, ""))

  // Live theme binding — updates when Commons.Color.accent changes.
  readonly property int dockDepth: Commons.Style.spacing.xs
    + Math.round(36 * Commons.Style.fontScale) + Commons.Style.spacing.md * 2
  property bool initialized: false
  property string backendPhase: "idle"
  property int workerDockDepth: 0
  property string setupProgress: "starting"
  readonly property string setupState: {
    if (backendPhase === "running") return "ready"
    if (backendPhase === "failed" || backendPhase === "degraded") return "error"
    return backendPhase === "starting" ? setupProgress : backendPhase
  }
  property string setupMessage: ""
  property bool rebuildRequested: false
  function retrySetup() {
    if (!backendEnabled) return
    rebuildRequested = true
    stopBackend()
  }
  function backendCommand() {
    var command = ["python3", root.pluginDir + "/runner.py"]
    if (rebuildRequested) command.push("--rebuild-observer")
    return command.concat(["--", "--snap", "--settings", appearance.configPath, "--dock-depth", String(root.dockDepth)])
  }
  function clearPreview() {
    previewVisible = false
    previewZone = ""
    previewMonitor = ""
    previewAddress = ""
    previewX = 0; previewY = 0; previewW = 0; previewH = 0
  }
  function scheduleRestart() {
    backendPhase = "backoff"
    restart.restart()
  }
  function stopBackend() {
    restart.stop()
    clearPreview()
    setupMessage = ""
    if (backendPhase === "stopping") return
    if (zonesd.running) {
      backendPhase = "stopping"
      zonesd.running = false
    } else if (backendEnabled) scheduleRestart()
    else backendPhase = "idle"
  }
  onBackendEnabledChanged: if (initialized) {
    if (backendEnabled && backendPhase !== "stopping") startBackend()
    if (!backendEnabled) {
      rebuildRequested = false
      stopBackend()
    }
  }
  Component.onDestruction: {
    restart.stop()
    zonesd.running = false
  }

  function startBackend() {
    if (!backendEnabled || zonesd.running || backendPhase === "stopping") return
    restart.stop()
    setupProgress = "starting"
    setupMessage = ""
    workerDockDepth = dockDepth
    zonesd.command = backendCommand()
    rebuildRequested = false
    backendPhase = "starting"
    zonesd.running = true
  }
  function backendExited(code) {
    clearPreview()
    if (!backendEnabled) backendPhase = "idle"
    else if (backendPhase !== "stopping" && code === 78) backendPhase = "failed"
    else scheduleRestart()
  }
  onDockDepthChanged: if (backendPhase === "running" || backendPhase === "degraded") {
    stopBackend()
  }
  Component.onCompleted: { initialized = true; startBackend() }

  Appearance { id: appearance }
  readonly property color shade: appearance.shade

  property bool previewVisible: false
  property string previewZone: ""
  property string previewMonitor: ""
  property string previewAddress: ""
  property int previewX: 0
  property int previewY: 0
  property int previewW: 0
  property int previewH: 0

  function handleZonesdLine(line) {
    if (backendPhase !== "starting" && backendPhase !== "running" && backendPhase !== "degraded") return
    var t = String(line || "").trim()
    if (!t.length || t.charAt(0) !== "{") {
      if (t.length) console.log("zones:", t)
      return
    }
    try {
      var msg = JSON.parse(t)
    } catch (e) {
      console.log("zones:", t)
      return
    }
    if (msg.event === "setup" && backendPhase === "starting") {
      setupProgress = msg.state || "error"
      setupMessage = msg.message || ""
    } else if (msg.event === "ready" && backendPhase === "starting") {
      // Theme metrics can settle while the native helper is being built.
      if (workerDockDepth !== dockDepth) stopBackend()
      else {
        backendPhase = "running"
        setupMessage = ""
      }
    } else if (msg.event === "warning" && String(msg.message).indexOf("Pointer observer unavailable") === 0) {
      backendPhase = "degraded"
      setupMessage = msg.message
      clearPreview()
    } else if (msg.event === "preview" && msg.rect && backendPhase === "running") {
      previewMonitor = msg.monitor || ""
      previewZone = msg.zone || ""
      previewAddress = msg.address || ""
      previewX = msg.rect.x || 0
      previewY = msg.rect.y || 0
      previewW = msg.rect.w || 0
      previewH = msg.rect.h || 0
      previewVisible = previewW > 0 && previewH > 0
    } else if (msg.event === "preview-clear") {
      clearPreview()
    } else if (msg.event === "snap-candidate") {
      console.log("zones: snap", msg.zone, JSON.stringify(msg.rect), msg.applied ? "applied" : "log-only")
    } else {
      console.log("zones:", t)
    }
  }

  Process {
    id: zonesd
    workingDirectory: root.pluginDir
    running: false
    stdout: SplitParser {
      onRead: function(line) { root.handleZonesdLine(line) }
    }
    stderr: StdioCollector {
      onStreamFinished: {
        var t = String(text || "").trim()
        if (t.length > 0) console.warn("zones:", t)
      }
    }
    onExited: function(code) { root.backendExited(code) }
  }

  Timer {
    id: restart
    interval: 2000
    onTriggered: root.startBackend()
  }

  // One overlay surface per output so global Hyprland logical coords map
  // correctly on multi-monitor setups. Empty mask → clicks pass through.
  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: previewWindow
      required property var modelData
      screen: modelData
      visible: root.previewVisible && previewWindow.onThisScreen
      color: "transparent"
      exclusionMode: ExclusionMode.Ignore

      WlrLayershell.namespace: "omarchy-zones-preview"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

      anchors { top: true; bottom: true; left: true; right: true }
      mask: Region {}

      readonly property int screenX: modelData.x
      readonly property int screenY: modelData.y
      readonly property int screenW: modelData.width
      readonly property int screenH: modelData.height

      // Zone rect is in global logical coords; convert to this output.
      readonly property bool onThisScreen: {
        var rx = root.previewX, ry = root.previewY
        var rw = root.previewW, rh = root.previewH
        return (!root.previewMonitor || root.previewMonitor === modelData.name) && rw > 0 && rh > 0
          && rx < screenX + screenW && rx + rw > screenX
          && ry < screenY + screenH && ry + rh > screenY
      }

      Rectangle {
        x: root.previewX - previewWindow.screenX
        y: root.previewY - previewWindow.screenY
        width: root.previewW
        height: root.previewH
        color: root.shade
        visible: previewWindow.onThisScreen
      }
    }
  }
}
