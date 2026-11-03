idf_component_register(SRCS "main.cpp" "calendar_engine.cpp" "network.cpp"
    INCLUDE_DIRS "."
    REQUIRES M5Unified M5GFX m5stack__m5pm1 nvs_flash esp_wifi esp_netif esp_http_server esp_event esp_timer esp_hw_support json)
target_add_binary_data(${COMPONENT_LIB} "assets/calendar.pack" BINARY)
