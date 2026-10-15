#!/usr/bin/env bash
set -euo pipefail
plugin_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
output="${1:-$plugin_dir/native/observer.so}"
output_dir="$(dirname -- "$output")"
mkdir -p -- "$output_dir"
# Build beside the plugin; no root installation or compositor changes.
read -r -a build_flags <<< "$(pkg-config --cflags hyprland libinput libudev pixman-1 wayland-server xkbcommon libdrm)"
read -r -a link_flags <<< "$(pkg-config --libs hyprland libinput libudev pixman-1 wayland-server xkbcommon libdrm)"
temporary_output="$(mktemp "$output_dir/.observer-XXXXXX.so")"
trap 'rm -f "$temporary_output"' EXIT
g++ -std=c++23 -shared -fPIC -fno-gnu-unique -O2 "${build_flags[@]}" \
    "$plugin_dir/native/pointer-observer.cpp" -o "$temporary_output" "${link_flags[@]}"
mv "$temporary_output" "$output"
