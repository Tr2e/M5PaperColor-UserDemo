#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
test_dir="$(mktemp -d "${TMPDIR:-/tmp}/papercolor-oil-tests.XXXXXX")"
# Includes compiler-generated .dSYM bundles on macOS; only this mktemp directory.
trap '[[ "$test_dir" == */papercolor-oil-tests.* ]] && rm -rf -- "$test_dir"' EXIT
test_binary="${test_dir}/painter"

clang++ -std=c++17 -O1 -g -Wall -Wextra -Werror \
    -fsanitize=address,undefined -fno-omit-frame-pointer \
    -I"${project_dir}/main" \
    "${project_dir}/main/display/papercolor_oil_painter.cpp" \
    "${project_dir}/tools/oil_paint_lab/test_oil_painter.cpp" \
    -o "${test_binary}"

"${test_binary}"

clang++ -std=c++17 -O1 -g -Wall -Wextra -Werror \
    -fsanitize=address,undefined -fno-omit-frame-pointer \
    -I"${project_dir}/tools/oil_paint_lab/stubs" -I"${project_dir}/main" \
    -I"${project_dir}/components/M5Unified/src" \
    "${project_dir}/main/display/papercolor_oil_painter.cpp" \
    "${project_dir}/main/apps/photo_effects/photo_effect_controller.cpp" \
    "${project_dir}/components/M5Unified/src/utility/Button_Class.cpp" \
    "${project_dir}/tools/oil_paint_lab/test_photo_effect_controller.cpp" \
    -o "${test_dir}/controller"

"${test_dir}/controller"
