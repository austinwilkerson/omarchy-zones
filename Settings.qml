import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import qs.Commons as Commons
import qs.Ui

Panel {
    id: root
    moduleName: "io.github.austinwilkerson.zones"
    ipcTarget: "zones"
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    readonly property color fg: Commons.Color.popups.text
    readonly property string family: bar ? bar.fontFamily : Commons.Style.font.family
    property bool manageBackend: true
    property var runtime: null
    Component.onCompleted: if (manageBackend) runtime = Runtime.acquire()
    Component.onDestruction: if (runtime) Runtime.release()
    property string page: "layout"
    Appearance { id: preferences }
    Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }
    onOpenedChanged: if (opened) {
        var window = button.QsWindow.window
        if (window && window.screen) layouts.monitorName = window.screen.name
    }
    BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "󰕰"
        tooltipText: strings.t("tooltip")
        onPressed: root.toggle()
    }
    component Label: Text {
        textFormat: Text.PlainText
        color: root.fg
        font.family: root.family
        font.pixelSize: Commons.Style.font.body
        wrapMode: Text.WordWrap
    }
    KeyboardPanel {
        anchorItem: button
        bar: root.bar
        owner: root
        open: root.opened
        focusTarget: content
        contentWidth: fittedContentWidth(Commons.Style.space(350))
        contentHeight: fittedContentHeight(body.implicitHeight, Commons.Style.space(740))
        Item {
            id: content
            anchors.fill: parent
            focus: true
            Keys.onEscapePressed: root.close()
            Flickable {
                anchors.fill: parent
                contentHeight: body.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Controls.ScrollBar.vertical: Controls.ScrollBar {}
                Column {
                    id: body
                    width: parent.width
                    spacing: Commons.Style.space(14)
                    PanelHero {
                        width: parent.width
                        title: strings.t("title")
                        meta: strings.t("subtitle")
                        foreground: root.fg
                        fontFamily: root.family
                    }
                    Label {
                        width: parent.width
                        visible: root.runtime && root.runtime.setupState !== "ready"
                        text: root.runtime && root.runtime.setupState === "error" ? root.runtime.setupMessage : strings.t("preparing")
                    }
                    Button {
                        visible: root.runtime && root.runtime.setupState === "error"
                        text: strings.t("retry")
                        bordered: true
                        foreground: root.fg
                        onClicked: root.runtime.retrySetup()
                    }
                    ButtonGroup {
                        width: parent.width
                        options: [{value:"layout",label:strings.t("layouts")},{value:"appearance",label:strings.t("appearance")}]
                        value: root.page
                        onChanged: value => root.page = value
                    }
                    LayoutSettings {
                        id: layouts
                        width: parent.width
                        visible: root.page === "layout"
                        active: root.opened && visible
                        appearance: preferences
                    }
                    Column {
                        width: parent.width
                        visible: root.page === "appearance"
                        spacing: Commons.Style.space(14)
                    Label { width: parent.width; text: strings.t("padding") }
                    Controls.SpinBox {
                        id: padding
                        from: 0; to: 64
                        value: preferences.gap
                        editable: true
                        palette.text: root.fg
                        palette.buttonText: root.fg
                        palette.base: Commons.Color.popups.background
                        palette.button: Commons.Color.popups.background
                        font.family: root.family
                        onValueModified: preferences.save({gap_px: value})
                    }
                    Label { width: parent.width; text: strings.t("padding_help"); opacity: .7 }
                    Label { text: strings.t("color") }
                    Row {
                        spacing: Commons.Style.space(8)
                        Repeater {
                            model: ["accent", "foreground", "urgent"]
                            Button {
                                required property string modelData
                                text: strings.t(modelData)
                                foreground: accent
                                fontFamily: root.family
                                selected: preferences.choice === modelData
                                bordered: true
                                iconText: "●"
                                accent: modelData === "accent" ? Commons.Color.accent : modelData === "foreground" ? Commons.Color.foreground : Commons.Color.urgent
                                onClicked: preferences.save({preview: {color: modelData}})
                            }
                        }
                    }
                    Button {
                        text: strings.t("custom")
                        foreground: root.fg
                        fontFamily: root.family
                        bordered: true
                        selected: preferences.choice === "custom"
                        onClicked: preferences.save({preview: {color: "custom"}})
                    }
                    Column {
                        visible: preferences.choice === "custom"
                        width: parent.width
                        spacing: Commons.Style.space(10)
                        ColorPicker {
                            width: parent.width
                            value: preferences.custom
                            onPicked: color => preferences.save({preview: {color: "custom", custom: color}})
                        }
                        Label { text: strings.t("hex") }
                        Row {
                            width: parent.width
                            spacing: Commons.Style.space(8)
                            Controls.TextField {
                                id: hex
                                width: Math.max(100, parent.width - apply.implicitWidth - parent.spacing)
                                text: preferences.custom
                                color: root.fg
                                font.family: root.family
                                validator: RegularExpressionValidator { regularExpression: /#[0-9a-fA-F]{6}/ }
                                onAccepted: if (acceptableInput) preferences.save({preview: {custom: text, color: "custom"}})
                            }
                            Button {
                                id: apply
                                text: strings.t("apply")
                                foreground: root.fg
                                bordered: true
                                enabled: hex.acceptableInput
                                onClicked: preferences.save({preview: {custom: hex.text, color: "custom"}})
                            }
                        }
                    }
                    Label { text: strings.t("opacity", "Opacity · %1%").arg(Commons.I18n.formatNumber(Math.round(opacity.value))) }
                    Controls.Slider {
                        id: opacity
                        width: parent.width
                        from: 5; to: 80; stepSize: 1
                        value: preferences.previewOpacity * 100
                        palette.highlight: Commons.Color.accent
                        onMoved: preferences.save({preview: {opacity: value / 100}})
                    }
                    Rectangle {
                        width: parent.width
                        height: Commons.Style.space(68)
                        color: Commons.Color.popups.background
                        border.width: 1
                        border.color: Commons.Color.muted
                        Rectangle { anchors.fill: parent; anchors.margins: 1; color: preferences.shade }
                        Label { anchors.centerIn: parent; text: strings.t("sample") }
                    }
                    Label { width: parent.width; text: preferences.error || strings.t("saved"); opacity: .7 }
                    }
                }
            }
        }
    }
}
