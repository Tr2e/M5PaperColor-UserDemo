/* SPDX-License-Identifier: MIT */
#pragma once

#include "display/papercolor_lut_display.h"
#include "display/papercolor_photo_dither.h"

constexpr size_t PAPERCOLOR_MAX_PHOTO_REGIONS = 2;

struct PaperColorRegionDither {
    PaperColorPhotoRegion rect;
    papercolor_dither_state_t dither;
};

// Validate before allocating or writing any display pixels. The home uses
// rotation 1; accepting all four unmirrored rotations keeps the API explicit.
inline bool papercolor_layout_photo_regions(const PaperColorPhotoRegion* input,
    size_t count, int32_t backing_width, int32_t backing_height, uint8_t rotation,
    PaperColorRegionDither* output, size_t& workspace_bytes)
{
    workspace_bytes = 0;
    if (count > PAPERCOLOR_MAX_PHOTO_REGIONS || rotation > 3 ||
        backing_width <= 0 || backing_width > 600 || backing_height <= 0 ||
        backing_height > 600 || (count && (!input || !output))) return false;
    const int32_t logical_w = (rotation & 1) ? backing_height : backing_width;
    const int32_t logical_h = (rotation & 1) ? backing_width : backing_height;
    for (size_t i = 0; i < count; ++i) {
        const auto& r = input[i];
        if (r.x < 0 || r.y < 0 || r.width <= 0 || r.height <= 0 ||
            r.x >= logical_w || r.y >= logical_h ||
            r.width > logical_w - r.x || r.height > logical_h - r.y) return false;
        auto& p = output[i].rect;
        switch (rotation) {
            case 1: p = {backing_width-r.y-r.height, r.x, r.height, r.width}; break;
            case 2: p = {backing_width-r.x-r.width, backing_height-r.y-r.height, r.width, r.height}; break;
            case 3: p = {r.y, backing_height-r.x-r.width, r.height, r.width}; break;
            default: p = r; break;
        }
        for (size_t j = 0; j < i; ++j) {
            const auto& q = output[j].rect;
            if (p.x < q.x+q.width && q.x < p.x+p.width &&
                p.y < q.y+q.height && q.y < p.y+p.height) return false;
        }
        workspace_bytes += papercolor_dither_workspace_size(p.width, PAPERCOLOR_DITHER_FLOYD_STEINBERG);
    }
    return true;
}

// Each region begins at local row zero and owns its error rows and target
// cache. UI pixels and neighboring images cannot contribute diffusion error.
inline bool papercolor_process_photo_regions_row(PaperColorRegionDither* regions,
    size_t count, int32_t y, const uint16_t* swap565, const uint8_t* rgb888,
    uint8_t* native)
{
    for (size_t i = 0; i < count; ++i) {
        auto& region = regions[i];
        const auto& r = region.rect;
        if (y < r.y || y >= r.y+r.height) continue;
        if (region.dither.row != static_cast<size_t>(y-r.y)) return false;
        const bool ok = swap565
            ? papercolor_dither_process_swap565_row(&region.dither, swap565+r.x, native+r.x)
            : papercolor_dither_process_rgb888_row(&region.dither, rgb888+r.x*3, native+r.x);
        if (!ok) return false;
    }
    return true;
}
