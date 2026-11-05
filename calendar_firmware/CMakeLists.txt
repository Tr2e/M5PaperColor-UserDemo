cmake_minimum_required(VERSION 3.16)
set(IDF_TARGET esp32s3)
set(PROJECT_VER "0.2.0")
# Share only hardware drivers with the sibling demo. No demo app/HAL is linked.
get_filename_component(PAPERCOLOR_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
list(APPEND CMAKE_MODULE_PATH "${PAPERCOLOR_ROOT}/managed_components/espressif__cmake_utilities")
set(EXTRA_COMPONENT_DIRS
    "${PAPERCOLOR_ROOT}/components/M5GFX"
    "${PAPERCOLOR_ROOT}/components/M5Unified"
    "${PAPERCOLOR_ROOT}/managed_components/m5stack__m5pm1"
    "${PAPERCOLOR_ROOT}/managed_components/espressif__i2c_bus"
    "${PAPERCOLOR_ROOT}/managed_components/espressif__cmake_utilities")
set(COMPONENTS main)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(tr2e_calendar)
