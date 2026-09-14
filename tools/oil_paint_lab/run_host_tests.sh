#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
test_binary="${TMPDIR:-/tmp}/papercolor_oil_painter_host_test"

clang++ -std=c++17 -O1 -g -Wall -Wextra -Werror \
    -fsanitize=address,undefined -fno-omit-frame-pointer \
    -I"${project_dir}/main" \
    "${project_dir}/main/display/papercolor_oil_painter.cpp" \
    "${project_dir}/tools/oil_paint_lab/test_oil_painter.cpp" \
    -o "${test_binary}"

"${test_binary}"
