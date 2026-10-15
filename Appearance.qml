import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons

Item {
    id: root
    property string baseConfigPath: decodeURIComponent(String(Qt.resolvedUrl("layouts.json")).replace(/^file:\/\//, ""))
    property string configPath: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/omarchy/zones/settings.json"
    property var defaults: ({})
    property var config: ({})
    property var pending: ({})
    property string error: ""
    readonly property int gap: Number.isInteger(config.gap_px) ? config.gap_px : 4
    readonly property var preview: config.preview || ({})
    readonly property string choice: preview.color || "accent"
    readonly property string custom: /^#[0-9a-fA-F]{6}$/.test(preview.custom || "") ? preview.custom : "#4488ff"
    readonly property real previewOpacity: typeof preview.opacity === "number" && isFinite(preview.opacity) ? Math.max(.05, Math.min(.8, preview.opacity)) : .35
    readonly property color baseColor: choice === "custom" ? custom : choice === "foreground" ? Commons.Color.foreground : choice === "urgent" ? Commons.Color.urgent : Commons.Color.accent
    readonly property color shade: Commons.Util.alpha(baseColor, previewOpacity)

    function merge(base, patch) {
        var next = Object.assign({}, base, patch)
        for (var key of ["preview", "monitors", "workspaces"]) {
            if (!base[key] && !patch[key]) continue
            var values = Object.assign({}, base[key] || {}, patch[key] || {})
            for (var name in values) if (values[name] === null) delete values[name]
            next[key] = values
        }
        return next
    }
    function layoutFor(monitor, workspace) {
        var specific = config.workspaces || {}
        return specific[monitor + ":" + workspace] || specific[String(workspace)] ||
            (config.monitors || {})[monitor] || config.default || "columns-mid50"
    }
    function load() {
        try {
            var override = JSON.parse(file.text() || "{}")
            config = merge(defaults, override)
            error = ""
        }
        catch (e) { error = "Could not read Zones settings." }
    }
    function save(patch) {
        config = merge(config, patch)
        var queued = Object.assign({}, pending, patch)
        for (var key of ["preview", "monitors", "workspaces"]) {
            if (patch[key]) queued[key] = Object.assign({}, pending[key] || {}, patch[key])
        }
        pending = queued
        debounce.restart()
    }
    function flush() {
        if (writer.running || !Object.keys(pending).length) return
        writer.command = ["python3", decodeURIComponent(String(Qt.resolvedUrl("settings.py")).replace(/^file:\/\//, "")), "--config", configPath, JSON.stringify(pending)]
        pending = ({})
        writer.running = true
    }
    FileView {
        id: base
        path: root.baseConfigPath
        watchChanges: true
        printErrors: false
        onLoaded: {
            try { root.defaults = JSON.parse(text()) } catch (e) { root.defaults = ({}) }
            root.load()
        }
        onFileChanged: reload()
    }
    FileView {
        id: file
        path: root.configPath
        watchChanges: true
        printErrors: false
        onLoaded: if (!writer.running && !Object.keys(root.pending).length) root.load()
        onFileChanged: reload()
        onLoadFailed: if (!writer.running) root.load()
    }
    Timer { id: debounce; interval: 250; onTriggered: root.flush() }
    Process {
        id: writer
        stderr: StdioCollector { onStreamFinished: if (text.trim()) root.error = text.trim() }
        onExited: function(code) {
            if (code === 0) root.error = ""
            file.reload()
            if (Object.keys(root.pending).length) debounce.restart()
        }
    }
}
