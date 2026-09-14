#pragma once

// Host substitutes for the controller's platform dependencies. The production
// controller and painter are compiled unchanged against these test headers.
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <vector>

namespace m5gfx { enum { rgb565_2Byte = 16 }; }
namespace oil_test {
inline int live_allocations = 0;
inline int allocation_attempts = 0;
inline int fail_allocation = 0;
inline int refreshes = 0;
inline int activities = 0;
inline bool refreshing = false;
inline int64_t now_us = 0;
inline int64_t timer_step_us = 0;
inline std::vector<uint32_t> delays;
template<class... Args> void log(const char*, const char*, Args...) {}
}

#define ESP_LOGI(...) oil_test::log(__VA_ARGS__)
#define ESP_LOGW(...) oil_test::log(__VA_ARGS__)
#define ESP_LOGE(...) oil_test::log(__VA_ARGS__)
constexpr unsigned MALLOC_CAP_SPIRAM = 1;
constexpr unsigned MALLOC_CAP_8BIT = 2;
inline void* heap_caps_malloc(size_t bytes, unsigned)
{
    if (++oil_test::allocation_attempts == oil_test::fail_allocation) return nullptr;
    void* result = std::malloc(bytes);
    if (result) ++oil_test::live_allocations;
    return result;
}
inline void heap_caps_free(void* pointer)
{
    if (pointer) --oil_test::live_allocations;
    std::free(pointer);
}
inline int64_t esp_timer_get_time()
{
    const int64_t result = oil_test::now_us;
    oil_test::now_us += oil_test::timer_step_us;
    return result;
}
using TickType_t = uint32_t;
#ifndef configTICK_RATE_HZ
#define configTICK_RATE_HZ 100
#endif
#define pdMS_TO_TICKS(ms) (static_cast<TickType_t>(ms) * configTICK_RATE_HZ / 1000U)
inline void vTaskDelay(TickType_t ticks)
{
    oil_test::delays.push_back(ticks);
    oil_test::now_us += ticks * 1000000ULL / configTICK_RATE_HZ;
}

struct TestCanvas {
    int backing_width = 32;
    int backing_height = 24;
    uint8_t rotation = 0;
    int depth = m5gfx::rgb565_2Byte;
    std::vector<uint16_t> pixels = std::vector<uint16_t>(32 * 24, 0xffff);
    int getColorDepth() const { return depth; }
    uint8_t getRotation() const { return rotation; }
    int width() const { return rotation & 1U ? backing_height : backing_width; }
    int height() const { return rotation & 1U ? backing_width : backing_height; }
    void* getBuffer() { return pixels.data(); }
    size_t bufferLength() const { return pixels.size() * sizeof(uint16_t); }
    void pushSprite(int, int) { ++oil_test::refreshes; }
};
enum { OPERATION_EVENT_REFRESH_START, OPERATION_EVENT_REFRESH_COMPLETE };
struct TestHal {
    TestCanvas* Canvas = nullptr;
    void statusEventSend(int) {}
};
inline TestHal hal;
inline void app_manager_set_refresh_in_progress(bool value) { oil_test::refreshing = value; }
inline void app_manager_mark_activity() { ++oil_test::activities; }
struct DisplayMetricsTrace {
    explicit DisplayMetricsTrace(const char*) {}
    void markRendered() {}
    void markRefreshStarted() {}
    void finish(bool) {}
};
