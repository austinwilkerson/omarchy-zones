import QtQuick
import QtQuick.Controls as Controls
import qs.Commons as Commons

// Embedded HSV picker avoids losing the settings popup to a separate dialog.
Column {
    id: root
    property color value: "#4488ff"
    property real hue: value.hsvHue < 0 ? 0 : value.hsvHue
    property real saturation: value.hsvSaturation
    property real brightness: value.hsvValue
    readonly property color selectedColor: Qt.hsva(hue, saturation, brightness, 1)
    onValueChanged: {
        hue = value.hsvHue < 0 ? 0 : value.hsvHue
        saturation = value.hsvSaturation
        brightness = value.hsvValue
    }
    signal picked(string color)
    spacing: Commons.Style.space(10)
    function commit() { picked(String(selectedColor)) }
    function select(x, y) {
        saturation = Math.max(0, Math.min(1, x / square.width))
        brightness = 1 - Math.max(0, Math.min(1, y / square.height))
    }
    Rectangle {
        id: square
        width: parent.width
        height: Commons.Style.space(130)
        color: Qt.hsva(root.hue, 1, 1, 1)
        Rectangle {
            anchors.fill: parent
            rotation: 0
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "white" }
                GradientStop { position: 1; color: "transparent" }
            }
        }
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0; color: "transparent" }
                GradientStop { position: 1; color: "black" }
            }
        }
        Rectangle {
            x: root.saturation * square.width - width / 2
            y: (1 - root.brightness) * square.height - height / 2
            width: 12; height: 12; radius: 6
            color: "transparent"; border.color: "white"; border.width: 2
        }
        MouseArea {
            anchors.fill: parent
            onPressed: mouse => root.select(mouse.x, mouse.y)
            onPositionChanged: mouse => { if (pressed) root.select(mouse.x, mouse.y) }
            onReleased: root.commit()
        }
    }
    Rectangle {
        width: parent.width
        height: Commons.Style.space(24)
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: "#ff0000" }
            GradientStop { position: 0.16667; color: "#ffff00" }
            GradientStop { position: 0.33333; color: "#00ff00" }
            GradientStop { position: 0.5; color: "#00ffff" }
            GradientStop { position: 0.66667; color: "#0000ff" }
            GradientStop { position: 0.83333; color: "#ff00ff" }
            GradientStop { position: 1; color: "#ff0000" }
        }
        Controls.Slider {
            anchors.fill: parent
            from: 0; to: 1; value: root.hue
            background: Item {}
            onMoved: root.hue = value
            onPressedChanged: if (!pressed) root.commit()
            onActiveFocusChanged: if (!activeFocus) root.commit()
        }
    }
}
