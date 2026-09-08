/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once

#include <cstddef>
#include <cstdint>

struct DisplayMetricsRecord {
    char source[32];
    bool success;
    uint64_t total_us;
    uint64_t render_us;
    uint64_t render_to_refresh_us;
    uint64_t panel_us;
    size_t internal_before;
    size_t internal_after;
    size_t internal_largest;
    size_t psram_before;
    size_t psram_after;
    size_t psram_largest;
};

/** Copies completed records in oldest-to-newest order. */
size_t displayMetricsSnapshot(DisplayMetricsRecord* records, size_t capacity);

/**
 * Records one high-level display operation without owning or synchronizing the
 * display. Each trace is local to its caller, so adding metrics does not change
 * the existing rendering or HTTP behavior.
 */
class DisplayMetricsTrace {
public:
    explicit DisplayMetricsTrace(const char* source);
    ~DisplayMetricsTrace();

    DisplayMetricsTrace(const DisplayMetricsTrace&)            = delete;
    DisplayMetricsTrace& operator=(const DisplayMetricsTrace&) = delete;

    /** Marks completion of decode/render work before the panel transfer. */
    void markRendered();

    /** Marks the point immediately before entering the synchronous EPD call. */
    void markRefreshStarted();

    /** Completes the trace and emits one structured log record. */
    void finish(bool success);

private:
    struct MemorySnapshot {
        size_t internal_free;
        size_t internal_largest;
        size_t psram_free;
        size_t psram_largest;
    };

    static MemorySnapshot captureMemory();

    const char* _source;
    uint64_t _started_us;
    uint64_t _rendered_us;
    uint64_t _refresh_started_us;
    MemorySnapshot _memory_before;
    bool _finished;
};
