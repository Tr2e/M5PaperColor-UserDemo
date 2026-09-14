// SPDX-License-Identifier: MIT
#pragma once

#include <cstddef>
#include <cstdint>

struct PaperColorOilRect {
    int x;
    int y;
    int width;
    int height;
};

struct PaperColorOilOptions {
    uint8_t coarse_radius = 14;
    uint8_t medium_radius = 7;
    uint8_t detail_radius = 3;
    uint8_t saturation_percent = 108;
    uint8_t contrast_percent = 108;
    uint32_t seed = 0x5041494eU;
    void (*cooperate)(void*) = nullptr;
    void* cooperate_context = nullptr;
};

struct PaperColorOilStats {
    uint32_t coarse_strokes = 0;
    uint32_t medium_strokes = 0;
    uint32_t detail_strokes = 0;
    size_t workspace_bytes = 0;
};

// RGB565 words use M5Canvas's byte-swapped memory representation.
uint16_t papercolor_oil_encode_swap565(uint8_t red, uint8_t green, uint8_t blue);
void papercolor_oil_decode_swap565(uint16_t pixel, uint8_t* red, uint8_t* green, uint8_t* blue);

size_t papercolor_oil_workspace_size(int content_width, int content_height);

// Source, destination and workspace must not overlap. Each image buffer must
// contain height * stride pixels. On invalid arguments, destination is
// untouched. On success, pixels outside content_rect are copied verbatim.
bool papercolor_oil_render_swap565(const uint16_t* source, uint16_t* destination,
                                   int width, int height, int stride,
                                   PaperColorOilRect content_rect,
                                   const PaperColorOilOptions& options,
                                   void* workspace, size_t workspace_size,
                                   PaperColorOilStats* stats);
