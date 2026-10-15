// SPDX-License-Identifier: MIT
// Observe button state without consuming input, changing windows, or adding binds.
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/managers/EventManager.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <stdexcept>

namespace {
CHyprSignalListener buttons;
bool left = false;
bool right = false;
unsigned long sequence = 0;

void publish() {
    if (g_pEventManager)
        g_pEventManager->postEvent({"omarchy-zones-pointer", std::format(
            R"({{"left":{},"right":{},"sequence":{}}})",left,right,sequence)});
}
}

APICALL EXPORT std::string PLUGIN_API_VERSION() { return HYPRLAND_API_VERSION; }

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE) {
    if (std::string(__hyprland_api_get_hash()) != std::string(__hyprland_api_get_client_hash()))
        throw std::runtime_error("Omarchy Zones observer: rebuild for the running Hyprland version");
    buttons = Event::bus()->m_events.input.mouse.button.listen(
        [](IPointer::SButtonEvent event, Event::SCallbackInfo&) {
            if (event.button != 272 && event.button != 273) return;
            const bool pressed = event.state == WL_POINTER_BUTTON_STATE_PRESSED;
            if (event.button == 272) left = pressed;
            else right = pressed;
            ++sequence;
            publish();
        });
    publish();
    return {"omarchy-zones-observer", "Read-only pointer state for Omarchy Zones", "Austin Wilkerson", "0.4.0"};
}

APICALL EXPORT void PLUGIN_EXIT() {
    buttons.reset();
    left = right = false;
    ++sequence;
    publish();
}
