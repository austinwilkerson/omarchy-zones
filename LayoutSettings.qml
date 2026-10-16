import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import qs.Ui

Column {
    id: root
    required property var appearance
    property bool active: false
    property string monitorName: ""
    property string scope: "monitor"
    property var monitors: []
    readonly property var selectedMonitor: monitors.find(m => m.name === monitorName) || null
    readonly property int workspace: selectedMonitor ? selectedMonitor.activeWorkspace.id : 0
    readonly property string selectedLayout: scope === "workspace" ? appearance.layoutFor(monitorName, workspace) :
        (appearance.config.monitors || {})[monitorName] || appearance.config.default || "columns-mid50"
    readonly property var presets: ["halves", "halves-vertical", "thirds", "thirds-vertical", "25-50-25", "quarters-cols", "grid-2x2", "columns-mid50"]
    spacing: Commons.Style.space(12)
    Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }
    function refresh() { if (!query.running) query.running = true }
    onActiveChanged: if (active) refresh()
    function choose(layout) {
        if (!monitorName || (scope === "workspace" && workspace <= 0)) return
        var values = {}
        values[scope === "workspace" ? monitorName + ":" + workspace : monitorName] = layout
        var patch = {}
        patch[scope === "workspace" ? "workspaces" : "monitors"] = values
        appearance.save(patch)
    }
    Process {
        id: query
        command: ["hyprctl", "monitors", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var result = JSON.parse(text)
                    if (!Array.isArray(result)) return
                    root.monitors = result
                    if (!root.selectedMonitor && result.length) root.monitorName = result[0].name
                } catch (e) { root.monitors = [] }
            }
        }
    }
    Timer { interval: 2000; repeat: true; running: root.active; onTriggered: root.refresh() }
    component Label: Text {
        textFormat: Text.PlainText
        color: Commons.Color.popups.text
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        wrapMode: Text.WordWrap
    }
    Label { text: strings.t("monitor") }
    ButtonGroup {
        width: parent.width
        options: root.monitors.map(m => ({value:m.name,label:m.name}))
        value: root.monitorName
        onChanged: value => root.monitorName = value
    }
    ButtonGroup {
        width: parent.width
        options: [{value:"monitor",label:strings.t("scope_monitor")},
                  {value:"workspace",label:strings.t("scope_workspace", "Workspace %1").arg(Commons.I18n.formatNumber(root.workspace))}]
        value: root.scope
        onChanged: value => root.scope = value
    }
    Label {
        width: parent.width
        text: root.scope === "workspace" ? strings.t("workspace_help") : strings.t("monitor_help")
        opacity: .7
    }
    Grid {
        width: parent.width
        columns: 2
        spacing: Commons.Style.space(10)
        Repeater {
            model: root.presets
            Rectangle {
                id: card
                required property string modelData
                readonly property bool selected: root.selectedLayout === modelData
                readonly property var zones: (root.appearance.config.layouts || {})[modelData] || []
                width: (parent.width - parent.spacing) / 2
                height: Commons.Style.space(100)
                color: selected ? Commons.Util.alpha(Commons.Color.accent, .1) : Commons.Color.popups.background
                border.width: selected ? 2 : 1
                border.color: selected ? Commons.Color.accent : Commons.Color.muted
                Item {
                    id: diagram
                    x: Commons.Style.space(10); y: x
                    width: parent.width - 2*x
                    height: Commons.Style.space(48)
                    Repeater {
                        model: card.zones
                        Rectangle {
                            required property var modelData
                            readonly property bool overlap: modelData.id === "mid50"
                            x: modelData.x * diagram.width + 1
                            y: modelData.y * diagram.height + 1
                            width: modelData.w * diagram.width - 2
                            height: modelData.h * diagram.height - 2
                            color: overlap ? Commons.Util.alpha(Commons.Color.accent, .5) : root.appearance.shade
                            border.color: Commons.Color.accent
                            border.width: overlap ? 2 : 1
                            // The center half covers two columns; its outline remains visible.
                            Text {
                                anchors.centerIn: parent
                                visible: parent.overlap
                                text: "50%"
                                textFormat: Text.PlainText
                                color: Commons.Color.popups.text
                                font.pixelSize: Commons.Style.font.caption
                            }
                        }
                    }
                }
                Label {
                    x: Commons.Style.space(6)
                    y: diagram.y + diagram.height + Commons.Style.space(6)
                    width: parent.width - 2*x
                    horizontalAlignment: Text.AlignHCenter
                    text: strings.t("layout_" + card.modelData)
                    font.pixelSize: Commons.Style.font.caption
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.choose(card.modelData)
                }
                activeFocusOnTab: true
                Keys.onReturnPressed: root.choose(card.modelData)
                Keys.onSpacePressed: root.choose(card.modelData)
                Rectangle { anchors.fill: parent; color: "transparent"; border.color: Commons.Color.accent; border.width: 2; visible: parent.activeFocus }
            }
        }
    }
    Button {
        visible: root.scope === "workspace" && !!(root.appearance.config.workspaces || {})[root.monitorName + ":" + root.workspace]
        text: strings.t("inherit")
        bordered: true
        foreground: Commons.Color.popups.text
        onClicked: root.choose(null)
    }
    Label { width: parent.width; text: strings.t("overlap_help"); opacity: .7 }
    Label {
        width: parent.width
        visible: root.scope === "monitor" && root.workspace > 0 &&
            root.appearance.layoutFor(root.monitorName,root.workspace) !== root.selectedLayout
        text: strings.t("workspace_override")
        color: Commons.Color.accent
    }
    Label { width: parent.width; visible: !!root.appearance.error; text: root.appearance.error }
}
