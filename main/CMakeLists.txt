set(APP_ASSETS_USE_EMBEDDED 1)

idf_component_register(
    SRCS
        "main.cpp"
        "display/display_metrics.cpp"
        "display/papercolor_lut.cpp"
        "display/papercolor_photo_dither.cpp"
        "display/papercolor_lut_display.cpp"
        "display/papercolor_native_chart.cpp"
        "display/papercolor_reference_photo.cpp"
        "display/papercolor_reference_chart.cpp"
        "display/papercolor_mix_chart.cpp"
        "display/papercolor_white_ab_chart.cpp"
        "display/papercolor_warm_ab_chart.cpp"
        "display/papercolor_purple_smooth_ab_chart.cpp"
        "display/papercolor_secondary_ratio_abc_chart.cpp"
        "display/papercolor_cyan_ratio_ab_chart.cpp"
        "apps/app_manager/app_manager.cpp"
        "apps/papercolor_home/papercolor_home.cpp"
        "apps/app_server/app_server.cpp"
        "hal/storage/hal_storage.cpp"
        "hal/ezdata/hal_ezdata.cpp"
        "hal/wifi/hal_wifi.cpp"
        "hal/hal.cpp"
        "apps/local_photo_slideshow/local_photo_slideshow.cpp"
        "apps/ezdata_photo_push/ezdata_photo_push.cpp"
        "hal/utils/image/image_utils.cpp"
        "hal/utils/audio/audio.cpp"
        "hal/utils/dns_server/dns_server.c"
    INCLUDE_DIRS
        "."
        "hal/utils/audio"
        "hal/utils/image"
        "hal/utils/dns_server"
    REQUIRES
        esp_http_server
        esp_wifi
        nvs_flash
        fatfs
        wear_levelling
        json
        esp_event
        esp_netif
        console
        M5Unified
        M5GFX
        tinyusb
        esp_http_client
        esp-tls
        json
        mqtt

)

target_compile_definitions(${COMPONENT_LIB} PRIVATE APP_ASSETS_USE_EMBEDDED=${APP_ASSETS_USE_EMBEDDED})

# Keep the application on the project's debuggable -Og profile, but compile
# the two measured per-pixel PaperColor stages with production optimization.
# Their behavior is covered by host equivalence/determinism tests.
set_source_files_properties(
    "display/papercolor_photo_dither.cpp"
    "display/papercolor_lut_display.cpp"
    PROPERTIES COMPILE_OPTIONS "-O2"
)

target_add_binary_data(${COMPONENT_LIB} "apps/app_server/index.html" TEXT)
target_add_binary_data(${COMPONENT_LIB} "assets/PaperColor.png" BINARY)
target_add_binary_data(${COMPONENT_LIB} "assets/arrowClickToPowerOn.png" BINARY)
target_add_binary_data(${COMPONENT_LIB} "assets/papercolor_web_logo.png" BINARY)

if(CONFIG_PAPERCOLOR_EXPERIMENTAL_LUT)
    target_add_binary_data(${COMPONENT_LIB} "../artifacts/color_lut/nominal-5bit.lut" BINARY)
endif()

if(CONFIG_PAPERCOLOR_REFERENCE_PHOTO_ON_BOOT)
    target_add_binary_data(${COMPONENT_LIB} "../artifacts/color_calibration/kodim04.png" BINARY)
endif()

if(CONFIG_PAPERCOLOR_REFERENCE_CHART_ON_BOOT)
    target_add_binary_data(${COMPONENT_LIB} "../artifacts/color_calibration/papercolor-calibration-v1.png" BINARY)
endif()

if(CONFIG_PAPERCOLOR_WHITE_AB_CHART_ON_BOOT)
    # Refuse stale pre-rendered crops after any source/payload change. Uses
    # built-in CMake hashing; no image libraries required in the IDF runtime.
    file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/../artifacts/color_calibration/white-ab-v1.sha256" WHITE_AB_INPUTS)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/../artifacts/color_calibration/white-ab-v1.sha256")
    foreach(ENTRY IN LISTS WHITE_AB_INPUTS)
        string(SUBSTRING "${ENTRY}" 0 64 EXPECTED_HASH)
        string(SUBSTRING "${ENTRY}" 65 -1 INPUT_PATH)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            "${CMAKE_CURRENT_SOURCE_DIR}/../${INPUT_PATH}")
        file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/../${INPUT_PATH}" ACTUAL_HASH)
        if(NOT ACTUAL_HASH STREQUAL EXPECTED_HASH)
            message(FATAL_ERROR "Stale white A/B input ${INPUT_PATH}; run tools/color_lab/generate_white_ab_chart.py")
        endif()
    endforeach()
    target_add_binary_data(${COMPONENT_LIB} "../artifacts/color_calibration/white-ab-v1.bin" BINARY)
endif()

if(CONFIG_PAPERCOLOR_WARM_AB_CHART_ON_BOOT)
    # Refuse stale pre-rendered crops after any source/payload change. Uses
    # built-in CMake hashing; no image libraries required in the IDF runtime.
    file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/../artifacts/color_calibration/warm-ab-v1.sha256" WARM_AB_INPUTS)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/../artifacts/color_calibration/warm-ab-v1.sha256")
    foreach(ENTRY IN LISTS WARM_AB_INPUTS)
        string(SUBSTRING "${ENTRY}" 0 64 EXPECTED_HASH)
        string(SUBSTRING "${ENTRY}" 65 -1 INPUT_PATH)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            "${CMAKE_CURRENT_SOURCE_DIR}/../${INPUT_PATH}")
        file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/../${INPUT_PATH}" ACTUAL_HASH)
        if(NOT ACTUAL_HASH STREQUAL EXPECTED_HASH)
            message(FATAL_ERROR "Stale warm A/B input ${INPUT_PATH}; run tools/color_lab/generate_warm_ab_chart.py")
        endif()
    endforeach()
    target_add_binary_data(${COMPONENT_LIB} "../artifacts/color_calibration/warm-ab-v1.bin" BINARY)
endif()

if(CONFIG_PAPERCOLOR_PURPLE_SMOOTH_AB_CHART_ON_BOOT)
    # Refuse stale pre-rendered crops after any source/payload change. Uses
    # built-in CMake hashing; no image libraries required in the IDF runtime.
    file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/../artifacts/color_calibration/purple-smooth-ab-v1.sha256" PURPLE_SMOOTH_AB_INPUTS)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/../artifacts/color_calibration/purple-smooth-ab-v1.sha256")
    foreach(ENTRY IN LISTS PURPLE_SMOOTH_AB_INPUTS)
        string(SUBSTRING "${ENTRY}" 0 64 EXPECTED_HASH)
        string(SUBSTRING "${ENTRY}" 65 -1 INPUT_PATH)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            "${CMAKE_CURRENT_SOURCE_DIR}/../${INPUT_PATH}")
        file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/../${INPUT_PATH}" ACTUAL_HASH)
        if(NOT ACTUAL_HASH STREQUAL EXPECTED_HASH)
            message(FATAL_ERROR "Stale purple smooth A/B input ${INPUT_PATH}; run tools/color_lab/generate_purple_smooth_ab_chart.py")
        endif()
    endforeach()
    target_add_binary_data(${COMPONENT_LIB} "../artifacts/color_calibration/purple-smooth-ab-v1.bin" BINARY)
endif()

if(CONFIG_PAPERCOLOR_SECONDARY_RATIO_ABC_CHART_ON_BOOT)
    # Refuse stale pre-rendered crops after any source/payload change. Uses
    # built-in CMake hashing; no image libraries required in the IDF runtime.
    file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/../artifacts/color_calibration/secondary-ratio-abc-v1.sha256" SECONDARY_RATIO_ABC_INPUTS)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/../artifacts/color_calibration/secondary-ratio-abc-v1.sha256")
    foreach(ENTRY IN LISTS SECONDARY_RATIO_ABC_INPUTS)
        string(SUBSTRING "${ENTRY}" 0 64 EXPECTED_HASH)
        string(SUBSTRING "${ENTRY}" 65 -1 INPUT_PATH)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            "${CMAKE_CURRENT_SOURCE_DIR}/../${INPUT_PATH}")
        file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/../${INPUT_PATH}" ACTUAL_HASH)
        if(NOT ACTUAL_HASH STREQUAL EXPECTED_HASH)
            message(FATAL_ERROR "Stale secondary ratio A/B/C input ${INPUT_PATH}; run tools/color_lab/generate_secondary_ratio_abc_chart.py")
        endif()
    endforeach()
    target_add_binary_data(${COMPONENT_LIB} "../artifacts/color_calibration/secondary-ratio-abc-v1.bin" BINARY)
endif()


if(CONFIG_PAPERCOLOR_CYAN_RATIO_AB_CHART_ON_BOOT)
    # Refuse stale pre-rendered crops after any source/payload change. Uses
    # built-in CMake hashing; no image libraries required in the IDF runtime.
    file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/../artifacts/color_calibration/cyan-ratio-ab-v1.sha256" CYAN_RATIO_AB_INPUTS)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/../artifacts/color_calibration/cyan-ratio-ab-v1.sha256")
    foreach(ENTRY IN LISTS CYAN_RATIO_AB_INPUTS)
        string(SUBSTRING "${ENTRY}" 0 64 EXPECTED_HASH)
        string(SUBSTRING "${ENTRY}" 65 -1 INPUT_PATH)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
            "${CMAKE_CURRENT_SOURCE_DIR}/../${INPUT_PATH}")
        file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/../${INPUT_PATH}" ACTUAL_HASH)
        if(NOT ACTUAL_HASH STREQUAL EXPECTED_HASH)
            message(FATAL_ERROR "Stale cyan ratio A/B input ${INPUT_PATH}; run tools/color_lab/generate_cyan_ratio_ab_chart.py")
        endif()
    endforeach()
    target_add_binary_data(${COMPONENT_LIB} "../artifacts/color_calibration/cyan-ratio-ab-v1.bin" BINARY)
endif()
