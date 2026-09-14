/* SPDX-License-Identifier: MIT */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include <initializer_list>

#include "display/papercolor_native_chart.h"

namespace papercolor_warm_ratio_abc_chart {
constexpr int WIDTH = 400;
constexpr int HEIGHT = 600;
constexpr int PATCH_WIDTH = 88;
constexpr int PATCH_HEIGHT = 50;
constexpr int ROW_COUNT = 6;
constexpr int COLUMN_X = 12;
constexpr int COLUMN_STEP = 96;
constexpr int ROW_Y = 118;
constexpr int ROW_STEP = 74;
constexpr size_t PATCH_BYTES = PATCH_WIDTH * PATCH_HEIGHT / 2;
constexpr size_t PAYLOAD_BYTES = ROW_COUNT * 3 * PATCH_BYTES;
constexpr int VARIANTS[] = {0, 1, 2, 0};
constexpr const char* LABELS[] = {
    "14 ORANGE RATIO B:+RED C:-RED",
    "15 RED ORANGE B:+RED C:-RED",
    "13 WARM YELLOW CONTROL",
    "09 DEEP PURPLE CONTROL",
    "12 TEAL CONTROL",
    "16 MAGENTA CONTROL",
};

inline bool valid_payload(const uint8_t* data, size_t size)
{
    if (!data || size != PAYLOAD_BYTES) return false;
    for (size_t index = 0; index < size; ++index) {
        for (uint8_t code : {uint8_t(data[index] >> 4), uint8_t(data[index] & 15)}) {
            if (code > 6 || code == 4) return false;
        }
    }
    return true;
}

inline bool sample(int x, int y, const uint8_t* data, size_t size, uint8_t& native)
{
    if (!data || size != PAYLOAD_BYTES || x < 0 || y < 0 || x >= WIDTH || y >= HEIGHT) return false;
    for (int index = 0; index < 6; ++index) {
        if (x >= 12 + index * 64 && x < 68 + index * 64 && y >= 52 && y < 72) {
            native = papercolor_native_chart::SOLIDS[index];
            return true;
        }
    }
    if (y < ROW_Y || x < COLUMN_X) return false;
    const int row = (y - ROW_Y) / ROW_STEP;
    const int patch_y = (y - ROW_Y) % ROW_STEP;
    const int column = (x - COLUMN_X) / COLUMN_STEP;
    const int patch_x = (x - COLUMN_X) % COLUMN_STEP;
    if (row >= ROW_COUNT || patch_y >= PATCH_HEIGHT || column >= 4 || patch_x >= PATCH_WIDTH) return false;
    const size_t pixel = patch_y * PATCH_WIDTH + patch_x;
    const uint8_t packed = data[(row * 3 + VARIANTS[column]) * PATCH_BYTES + pixel / 2];
    native = (pixel & 1) ? packed & 15 : packed >> 4;
    return true;
}
}  // namespace papercolor_warm_ratio_abc_chart

bool papercolor_show_warm_ratio_abc_chart();
