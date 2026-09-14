// SPDX-License-Identifier: MIT
#pragma once
#include "papercolor_oil_painter.h"

struct PaperColorStackedOptions {
    uint32_t seed = 0x5041494eU;
    void (*cooperate)(void*) = nullptr;
    void* cooperate_context = nullptr;
};

struct PaperColorStackedStats {
    uint32_t strokes[5] = {};
    size_t workspace_bytes = 0;
};

// Fixed-capacity caller-owned workspace. No malloc/vector/stable_sort inside
// the renderer. Supports content rectangles up to 600x600, including portraits.
size_t papercolor_stacked_workspace_size(int content_width, int content_height);

// Native M5Canvas byte-swapped RGB565. Buffers must not overlap. Source and
// destination require uint16_t alignment, workspace requires uint32_t alignment.
// Each frame holds height*stride pixels. Invalid inputs leave destination and
// stats untouched; success preserves padding and pixels outside content_rect.
bool papercolor_stacked_render_swap565(const uint16_t* source, uint16_t* destination,
    int width, int height, int stride, PaperColorOilRect content_rect,
    const PaperColorStackedOptions& options, void* workspace, size_t workspace_size,
    PaperColorStackedStats* stats = nullptr);
