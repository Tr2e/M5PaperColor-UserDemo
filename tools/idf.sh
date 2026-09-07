#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"

# PaperMono already uses this ESP-IDF checkout and the matching toolchain in
# the common Espressif tools directory. Override PAPERCOLOR_IDF_PATH if the
# shared checkout is moved.
shared_idf_default="${project_dir}/../stopwatch/esp-idf"
shared_idf="${PAPERCOLOR_IDF_PATH:-${IDF_PATH:-${shared_idf_default}}}"

if [[ ! -f "${shared_idf}/export.sh" ]]; then
    if [[ -n "${IDF_PATH:-}" && -f "${IDF_PATH}/export.sh" ]]; then
        shared_idf="${IDF_PATH}"
    else
        echo "PaperColor: ESP-IDF not found at ${shared_idf}" >&2
        echo "Set PAPERCOLOR_IDF_PATH to the ESP-IDF checkout used by PaperMono." >&2
        exit 1
    fi
fi

# export.sh configures PATH, the Python environment and the installed tools.
# shellcheck disable=SC1090
source "${shared_idf}/export.sh" >/dev/null

idf_version="$(idf.py --version)"
case "${idf_version}" in
    "ESP-IDF v5.5."*) ;;
    *)
        echo "PaperColor: expected ESP-IDF 5.5.x, found ${idf_version}" >&2
        exit 1
        ;;
esac

cd "${project_dir}"
exec idf.py "$@"
