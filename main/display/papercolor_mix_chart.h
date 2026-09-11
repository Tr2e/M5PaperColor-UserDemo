/* SPDX-License-Identifier: MIT */
#pragma once
#include "display/papercolor_native_chart.h"

// Direct native-code experiment. Column ratios apply only to the non-white
// pixels, so white coverage and chromatic balance are independent variables.
namespace papercolor_mix_chart {
constexpr int WIDTH = 400, HEIGHT = 600;
constexpr int PATCH_WIDTH = 64, PATCH_HEIGHT = 32;
constexpr int COLUMN_X = 48, COLUMN_STEP = 68;
constexpr int ROW_STEP = 44, PANEL_Y[] = {126, 344};
constexpr int CHROMATIC_EIGHTHS[] = {2,3,4,5,6};
constexpr const char* COLUMN_LABELS[] = {"25%","37.5%","50%","62.5%","75%"};
constexpr const char* WHITE_LABELS[] = {"W 0%","W12.5%","W 25%","W37.5%"};
constexpr uint8_t FIRST_PIGMENT[] = {3,6};

// Rank permutation 0..127 on a 16x8 tile, derived from the existing Bayer
// reference pattern. All grid patches use this same phase and arrangement.
constexpr int rank(int x, int y)
{
    constexpr int quadrant[2][2] = {{0,2},{3,1}};
    const int bayer8 = 4 * papercolor_native_chart::RANK[y & 3][x & 3] +
                       quadrant[(y >> 2) & 1][(x >> 2) & 1];
    return 2 * bayer8 + ((x >> 3) & 1);
}

inline bool sample(int x, int y, uint8_t& native)
{
    if (x < 0 || y < 0 || x >= WIDTH || y >= HEIGHT) return false;
    for (int i = 0; i < 6; ++i) {
        const int left = 12 + i * 64;
        if (x >= left && x < left + 56 && y >= 54 && y < 78) {
            native = papercolor_native_chart::SOLIDS[i];
            return true;
        }
    }
    for (int panel = 0; panel < 2; ++panel) {
        for (int row = 0; row < 4; ++row) {
            const int top = PANEL_Y[panel] + row * ROW_STEP;
            if (y < top || y >= top + PATCH_HEIGHT) continue;
            for (int col = 0; col < 5; ++col) {
                const int left = COLUMN_X + col * COLUMN_STEP;
                if (x < left || x >= left + PATCH_WIDTH) continue;
                const int white = row * 16;
                const int first = (128 - white) * CHROMATIC_EIGHTHS[col] / 8;
                const int value = rank(x-left, y-top);
                native = value < white ? 1 :
                         (value < white + first ? FIRST_PIGMENT[panel] : 5);
                return true;
            }
        }
    }
    return false;
}
} // namespace papercolor_mix_chart

bool papercolor_show_mix_chart();
