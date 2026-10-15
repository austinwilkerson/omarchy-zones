pragma Singleton
import QtQuick

QtObject {
    id: root
    property int users: 0
    readonly property QtObject coordinator: Service { backendEnabled: false }
    function acquire() {
        users++
        if (users === 1) coordinator.backendEnabled = true
        return coordinator
    }
    function release() {
        users = Math.max(0, users - 1)
        if (!users) coordinator.backendEnabled = false
    }
}
