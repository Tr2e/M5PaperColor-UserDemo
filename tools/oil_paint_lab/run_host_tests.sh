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

clang++ -std=c++17 -O2 -ffp-contract=off -g -Wall -Wextra -Werror \
    -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer \
    -I"${project_dir}/main" \
    "${project_dir}/main/display/papercolor_oil_painter.cpp" \
    "${project_dir}/main/display/papercolor_stacked_painter.cpp" \
    "${project_dir}/tools/oil_paint_lab/test_stacked_painter.cpp" \
    -o "${test_dir}/stacked"
"${test_dir}/stacked"

for stacked in 0 1; do
for tick_hz in 100 1000; do
    clang++ -std=c++17 -O1 -g -Wall -Wextra -Werror -DconfigTICK_RATE_HZ="${tick_hz}" \
        -DCONFIG_PAPERCOLOR_OIL_PAINT_STACKED="${stacked}" \
        -fsanitize=address,undefined -fno-omit-frame-pointer \
        -I"${project_dir}/tools/oil_paint_lab/stubs" -I"${project_dir}/main" \
        -I"${project_dir}/components/M5Unified/src" \
        "${project_dir}/main/display/papercolor_oil_painter.cpp" \
        "${project_dir}/main/display/papercolor_stacked_painter.cpp" \
        "${project_dir}/main/apps/photo_effects/photo_effect_controller.cpp" \
        "${project_dir}/components/M5Unified/src/utility/Button_Class.cpp" \
        "${project_dir}/tools/oil_paint_lab/test_photo_effect_controller.cpp" \
        -o "${test_dir}/controller"

    "${test_dir}/controller"
done
done
