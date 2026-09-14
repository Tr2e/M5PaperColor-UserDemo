#!/usr/bin/env bash
set -euo pipefail

variant="${1:-}"
if [[ "$variant" != on && "$variant" != off ]] || (( $# > 2 )); then
    echo "Usage: bash tools/oil_paint_lab/build_firmware.sh on|off [build-directory]" >&2
    exit 2
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
build_dir="${2:-${project_dir}/build/oil-${variant}}"
mkdir -p "$build_dir"
build_dir="$(cd "$build_dir" && pwd)"
if [[ "$build_dir" == "$project_dir" ]]; then
    echo "Choose a separate build directory; the project sdkconfig is not a build variant." >&2
    exit 2
fi

defaults="${project_dir}/sdkconfig.defaults"
if [[ "$variant" == on ]]; then
    defaults+=";${project_dir}/tools/oil_paint_lab/oil-paint-sdkconfig.defaults"
fi

# Each variant has its own sdkconfig; SDKCONFIG_DEFAULTS alone cannot override
# values already stored in the user's project-level configuration.
"${project_dir}/tools/idf.sh" -B "$build_dir" \
    -D "SDKCONFIG=${build_dir}/sdkconfig" \
    -D "SDKCONFIG_DEFAULTS=${defaults}" reconfigure

header="${build_dir}/config/sdkconfig.h"
if [[ ! -f "$header" ]]; then
    echo "Missing generated configuration: $header" >&2
    exit 1
fi
enabled=off
if grep -q '^#define CONFIG_PAPERCOLOR_OIL_PAINT 1$' "$header"; then
    enabled=on
fi
if [[ "$enabled" != "$variant" ]]; then
    echo "Oil-paint configuration mismatch: requested $variant, generated $enabled." >&2
    echo "Use a fresh build directory or adjust ${build_dir}/sdkconfig with menuconfig." >&2
    exit 1
fi

echo "Verified oil-paint=$enabled with isolated config ${build_dir}/sdkconfig"
"${project_dir}/tools/idf.sh" -B "$build_dir" build
