/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>

// Geometry and exact native-code mixtures shared by the diagnostic renderer
// and host tests. This chart never passes through the photo LUT or diffuser.
namespace papercolor_native_chart {
constexpr int WIDTH = 400, HEIGHT = 600;
constexpr uint8_t SOLIDS[] = {0, 1, 2, 3, 5, 6};
constexpr const char* NAMES[] = {"BLACK 0", "WHITE 1", "YELLOW 2", "RED 3", "BLUE 5", "GREEN 6"};
constexpr uint8_t PAIRS[][2] = {{3,1}, {3,5}, {5,6}, {3,2}, {0,1}, {6,1}};
constexpr const char* PAIR_NAMES[] = {"RED / WHITE", "RED / BLUE", "BLUE / GREEN",
                                    "RED / YELLOW", "BLACK / WHITE", "GREEN / WHITE"};
constexpr uint8_t RGB[7][3] = {{0,0,0}, {255,255,255}, {255,243,56}, {191,0,0},
                              {255,255,255}, {100,64,255}, {67,138,28}};
constexpr uint8_t RANK[4][4] = {{0,8,2,10}, {12,4,14,6}, {3,11,1,9}, {15,7,13,5}};

inline bool sample(int x, int y, uint8_t& native)
{
    for (int i = 0; i < 6; ++i) {
        const int left = 12 + (i % 3) * 128, top = 58 + (i / 3) * 78;
        if (x >= left && x < left + 120 && y >= top && y < top + 48) {
            native = SOLIDS[i];
            return true;
        }
    }
    for (int row = 0; row < 6; ++row) {
        const int top = 234 + row * 50;
        if (y < top || y >= top + 32) continue;
        for (int col = 0; col < 5; ++col) {
            const int left = 12 + col * 76;
            if (x >= left && x < left + 72) {
                // Every complete 4x4 cell contains exactly 0/4/8/12/16
                // pixels of the second pigment, not a desired source RGB.
                native = PAIRS[row][RANK[(y-top) & 3][(x-left) & 3] < col * 4 ? 1 : 0];
                return true;
            }
        }
    }
    return false;
}
} // namespace papercolor_native_chart

/** Startup-only diagnostic; false on disabled builds or allocation failure. */
bool papercolor_show_native_chart();
