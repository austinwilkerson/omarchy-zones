// SPDX-License-Identifier: MIT
// Observe button state without consuming input, changing windows, or adding binds.
#include <hyprland/src/plugins/PluginAPI.hpp>
#if __has_include(<hyprland/src/ipc/s2/S2.hpp>)
#include <hyprland/src/ipc/s2/S2.hpp>
#else
#include <hyprland/src/managers/EventManager.hpp>
#endif
#include <hyprland/src/event/EventBus.hpp>
#include <format>
#include <stdexcept>
#include <utility>

namespace {
CHyprSignalListener buttons;
bool left = false;
bool right = false;
unsigned long sequence = 0;

void publish() {
    auto data = std::format(R"({{"left":{},"right":{},"sequence":{}}})", left, right, sequence);
#if __has_include(<hyprland/src/ipc/s2/S2.hpp>)
    if (auto& socket = IPC::Socket2::sock(); socket)
        socket->postEvent({"omarchy-zones-pointer", std::move(data)});
#else
    if (g_pEventManager)
        g_pEventManager->postEvent({"omarchy-zones-pointer", std::move(data)});
#endif
}
}

APICALL EXPORT std::string PLUGIN_API_VERSION() { return HYPRLAND_API_VERSION; }

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE) {
    if (std::string(__hyprland_api_get_hash()) != std::string(__hyprland_api_get_client_hash()))
        throw std::runtime_error("Floating Snap Zones observer: rebuild for the running Hyprland version");
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
    return {"omarchy-zones-observer", "Read-only pointer state for Floating Snap Zones", "Austin Wilkerson", "0.4.4"};
}

APICALL EXPORT void PLUGIN_EXIT() {
    buttons.reset();
    left = right = false;
    ++sequence;
    publish();
}
