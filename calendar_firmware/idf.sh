#!/usr/bin/env bash
set -euo pipefail
calendar_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
calendar_idf="${PAPERCOLOR_IDF_PATH:-${IDF_PATH:-${calendar_dir}/../../stopwatch/esp-idf}}"
if [[ ! -f "${calendar_idf}/export.sh" ]]; then
    echo "Set PAPERCOLOR_IDF_PATH to ESP-IDF 5.5.x" >&2
    exit 1
fi
source "${calendar_idf}/export.sh" >/dev/null
case "$(idf.py --version)" in "ESP-IDF v5.5."*) ;; *) echo "ESP-IDF 5.5.x required" >&2; exit 1;; esac
# Use already installed, pinned sibling hardware components without downloading
# the demo's USB storage, MQTT, cloud, QR or other application dependencies.
export IDF_COMPONENT_MANAGER=0
cd "${calendar_dir}"
exec idf.py "$@"
