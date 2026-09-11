/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <initializer_list>
#include "display/papercolor_native_chart.h"

namespace papercolor_warm_ab_chart {
constexpr int WIDTH=400, HEIGHT=600;
constexpr int PATCH_WIDTH=88, PATCH_HEIGHT=50, ROW_COUNT=6;
constexpr int COLUMN_X=12, COLUMN_STEP=96, ROW_Y=118, ROW_STEP=74;
constexpr size_t PATCH_BYTES=PATCH_WIDTH*PATCH_HEIGHT/2;
constexpr size_t PAYLOAD_BYTES=ROW_COUNT*2*PATCH_BYTES;
constexpr int VARIANTS[]={0,1,1,0}; // A / B / B / A, identical duplicate crops.
constexpr int IDS[]={14,13,15,10,19,22};
constexpr const char* LABELS[]={"14 ORANGE  255,102,51","13 YELLOW  255,204,0",
    "15 RED ORANGE  204,51,0","10 BLUE CYAN  0,173,254",
    "19 BLUE CONTROL  0,0,255","22 GRAY CONTROL  96,96,96"};

inline bool valid_payload(const uint8_t* data, size_t size)
{
    if (!data || size!=PAYLOAD_BYTES) return false;
    for (size_t i=0;i<size;++i) {
        for (uint8_t code : {uint8_t(data[i]>>4),uint8_t(data[i]&15)})
            if (code>6 || code==4) return false;
    }
    return true;
}

// Crops are pre-rendered by the actual PhotoBalanced implementation, including
// RGB565 conversion and complete source-chart diffusion context. Never scale,
// recolor or dither these codes a second time on the device.
inline bool sample(int x, int y, const uint8_t* data, size_t size, uint8_t& native)
{
    if (!data || size!=PAYLOAD_BYTES || x<0 || y<0 || x>=WIDTH || y>=HEIGHT) return false;
    for (int i=0;i<6;++i) {
        if (x>=12+i*64 && x<68+i*64 && y>=52 && y<72) {
            native=papercolor_native_chart::SOLIDS[i];
            return true;
        }
    }
    if (y<ROW_Y || x<COLUMN_X) return false;
    const int row=(y-ROW_Y)/ROW_STEP, py=(y-ROW_Y)%ROW_STEP;
    const int col=(x-COLUMN_X)/COLUMN_STEP, px=(x-COLUMN_X)%COLUMN_STEP;
    if (row>=ROW_COUNT || py>=PATCH_HEIGHT || col>=4 || px>=PATCH_WIDTH) return false;
    const size_t pixel=py*PATCH_WIDTH+px;
    const uint8_t packed=data[(row*2+VARIANTS[col])*PATCH_BYTES+pixel/2];
    native=(pixel&1) ? packed&15 : packed>>4;
    return true;
}
} // namespace papercolor_warm_ab_chart

bool papercolor_show_warm_ab_chart();
