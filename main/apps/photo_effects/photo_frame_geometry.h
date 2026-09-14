// SPDX-License-Identifier: MIT
#pragma once

#include <algorithm>
#include <cstdint>

#include "display/papercolor_oil_painter.h"

// Convert the visible logical AspectFit rectangle into the unrotated Canvas
// backing-buffer coordinate system used by pushSprite().
inline bool papercolor_photo_backing_rect(int logical_width, int logical_height,
                                          uint8_t rotation, PaperColorOilRect draw,
                                          PaperColorOilRect* backing)
{
    if (!backing || logical_width <= 0 || logical_height <= 0 ||
        draw.width <= 0 || draw.height <= 0) return false;
    const int x0 = std::max(0, draw.x);
    const int y0 = std::max(0, draw.y);
    const int64_t far_x = static_cast<int64_t>(draw.x) + draw.width;
    const int64_t far_y = static_cast<int64_t>(draw.y) + draw.height;
    const int x1 = static_cast<int>(std::min<int64_t>(logical_width, far_x));
    const int y1 = static_cast<int>(std::min<int64_t>(logical_height, far_y));
    if (x0 >= x1 || y0 >= y1) return false;
    const int w = x1 - x0;
    const int h = y1 - y0;
    const int backing_width = rotation & 1U ? logical_height : logical_width;
    const int backing_height = rotation & 1U ? logical_width : logical_height;
    switch (rotation & 3U) {
        case 1: *backing = {backing_width - (y1), x0, h, w}; break;
        case 2: *backing = {backing_width - x1, backing_height - y1, w, h}; break;
        case 3: *backing = {y0, backing_height - x1, h, w}; break;
        default: *backing = {x0, y0, w, h}; break;
    }
    return backing->x >= 0 && backing->y >= 0 &&
           backing->x + backing->width <= backing_width &&
           backing->y + backing->height <= backing_height;
}
