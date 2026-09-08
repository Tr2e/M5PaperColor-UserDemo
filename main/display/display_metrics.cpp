/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "display/display_metrics.h"

#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"

#include <cstring>

namespace {

constexpr const char* TAG = "DisplayMetrics";
constexpr size_t METRICS_CAPACITY = 16;

portMUX_TYPE g_metrics_mux = portMUX_INITIALIZER_UNLOCKED;
DisplayMetricsRecord g_metrics[METRICS_CAPACITY]{};
size_t g_metrics_next  = 0;
size_t g_metrics_count = 0;

uint64_t elapsedUs(uint64_t end, uint64_t begin)
{
    return end >= begin ? end - begin : 0;
}

void storeRecord(const DisplayMetricsRecord& record)
{
    portENTER_CRITICAL(&g_metrics_mux);
    g_metrics[g_metrics_next] = record;
    g_metrics_next            = (g_metrics_next + 1) % METRICS_CAPACITY;
    if (g_metrics_count < METRICS_CAPACITY) {
        ++g_metrics_count;
    }
    portEXIT_CRITICAL(&g_metrics_mux);
}

}  // namespace

size_t displayMetricsSnapshot(DisplayMetricsRecord* records, size_t capacity)
{
    if (!records || capacity == 0) {
        return 0;
    }

    portENTER_CRITICAL(&g_metrics_mux);
    const size_t count = g_metrics_count < capacity ? g_metrics_count : capacity;
    const size_t oldest = (g_metrics_next + METRICS_CAPACITY - g_metrics_count) % METRICS_CAPACITY;
    const size_t skip   = g_metrics_count - count;
    for (size_t i = 0; i < count; ++i) {
        records[i] = g_metrics[(oldest + skip + i) % METRICS_CAPACITY];
    }
    portEXIT_CRITICAL(&g_metrics_mux);
    return count;
}

DisplayMetricsTrace::DisplayMetricsTrace(const char* source)
    : _source(source ? source : "unknown"),
      _started_us(static_cast<uint64_t>(esp_timer_get_time())),
      _rendered_us(0),
      _refresh_started_us(0),
      _memory_before(captureMemory()),
      _finished(false)
{
}

DisplayMetricsTrace::~DisplayMetricsTrace()
{
    if (!_finished) {
        finish(false);
    }
}

void DisplayMetricsTrace::markRendered()
{
    if (!_finished && _rendered_us == 0) {
        _rendered_us = static_cast<uint64_t>(esp_timer_get_time());
    }
}

void DisplayMetricsTrace::markRefreshStarted()
{
    if (_finished || _refresh_started_us != 0) {
        return;
    }
    if (_rendered_us == 0) {
        markRendered();
    }
    _refresh_started_us = static_cast<uint64_t>(esp_timer_get_time());
}

void DisplayMetricsTrace::finish(bool success)
{
    if (_finished) {
        return;
    }

    const uint64_t finished_us = static_cast<uint64_t>(esp_timer_get_time());
    if (_rendered_us == 0) {
        _rendered_us = finished_us;
    }
    if (_refresh_started_us == 0) {
        _refresh_started_us = finished_us;
    }

    const MemorySnapshot memory_after = captureMemory();
    DisplayMetricsRecord record{};
    strlcpy(record.source, _source, sizeof(record.source));
    record.success              = success;
    record.total_us             = elapsedUs(finished_us, _started_us);
    record.render_us            = elapsedUs(_rendered_us, _started_us);
    record.render_to_refresh_us = elapsedUs(_refresh_started_us, _rendered_us);
    record.panel_us             = elapsedUs(finished_us, _refresh_started_us);
    record.internal_before      = _memory_before.internal_free;
    record.internal_after       = memory_after.internal_free;
    record.internal_largest     = memory_after.internal_largest;
    record.psram_before         = _memory_before.psram_free;
    record.psram_after          = memory_after.psram_free;
    record.psram_largest        = memory_after.psram_largest;
    storeRecord(record);

    ESP_LOGI(TAG,
             "source=%s success=%u total_us=%llu render_us=%llu render_to_refresh_us=%llu panel_us=%llu "
             "internal_before=%u internal_after=%u internal_largest=%u psram_before=%u psram_after=%u "
             "psram_largest=%u",
             record.source, record.success ? 1U : 0U, static_cast<unsigned long long>(record.total_us),
             static_cast<unsigned long long>(record.render_us),
             static_cast<unsigned long long>(record.render_to_refresh_us),
             static_cast<unsigned long long>(record.panel_us),
             static_cast<unsigned>(_memory_before.internal_free), static_cast<unsigned>(memory_after.internal_free),
             static_cast<unsigned>(memory_after.internal_largest), static_cast<unsigned>(_memory_before.psram_free),
             static_cast<unsigned>(memory_after.psram_free), static_cast<unsigned>(memory_after.psram_largest));
    _finished = true;
}

DisplayMetricsTrace::MemorySnapshot DisplayMetricsTrace::captureMemory()
{
    return {
        heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
        heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
        heap_caps_get_free_size(MALLOC_CAP_SPIRAM),
        heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM),
    };
}
