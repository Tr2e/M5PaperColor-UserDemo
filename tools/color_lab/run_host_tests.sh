#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
test_binary="${TMPDIR:-/tmp}/papercolor_lut_host_test"

c++ -std=c++17 -O3 -Wall -Wextra -Werror \
    -I"${project_dir}/main" \
    "${project_dir}/main/display/papercolor_lut.cpp" \
    "${project_dir}/main/display/papercolor_photo_dither.cpp" \
    "${project_dir}/tools/color_lab/test_papercolor_lut.cpp" \
    -o "${test_binary}"

"${test_binary}" "${project_dir}/artifacts/color_lut/nominal-5bit.lut"
