/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "display/papercolor_lut.h"

namespace {

inline uint8_t lookup(const uint8_t* lut, const uint8_t* pixel, bool bgr)
{
    const uint8_t red   = pixel[bgr ? 2 : 0];
    const uint8_t green = pixel[1];
    const uint8_t blue  = pixel[bgr ? 0 : 2];
    return lut[papercolor_lut_index(red, green, blue)];
}

void quantize(const uint8_t* pixels, size_t pixel_count, uint8_t* packed, const uint8_t* lut, bool bgr)
{
    if (!pixels || !packed || !lut) {
        return;
    }

    for (size_t pixel = 0; pixel < pixel_count; pixel += 2) {
        const uint8_t first = lookup(lut, pixels + pixel * 3, bgr);
        uint8_t second      = PAPERCOLOR_NATIVE_WHITE;
        if (pixel + 1 < pixel_count) {
            second = lookup(lut, pixels + (pixel + 1) * 3, bgr);
        }
        packed[pixel >> 1] = static_cast<uint8_t>((first << 4) | second);
    }
}

}  // namespace

size_t papercolor_lut_index(uint8_t red, uint8_t green, uint8_t blue)
{
    return (static_cast<size_t>(red >> (8U - PAPERCOLOR_LUT_BITS)) << (PAPERCOLOR_LUT_BITS * 2U)) |
           (static_cast<size_t>(green >> (8U - PAPERCOLOR_LUT_BITS)) << PAPERCOLOR_LUT_BITS) |
           static_cast<size_t>(blue >> (8U - PAPERCOLOR_LUT_BITS));
}

uint8_t papercolor_lut_lookup(const uint8_t* lut, uint8_t red, uint8_t green, uint8_t blue)
{
    return lut ? lut[papercolor_lut_index(red, green, blue)]
               : static_cast<uint8_t>(PAPERCOLOR_NATIVE_WHITE);
}

void papercolor_quantize_rgb888_4bpp(const uint8_t* rgb, size_t pixel_count, uint8_t* packed,
                                     const uint8_t* lut)
{
    quantize(rgb, pixel_count, packed, lut, false);
}

void papercolor_quantize_bgr888_4bpp(const uint8_t* bgr, size_t pixel_count, uint8_t* packed,
                                     const uint8_t* lut)
{
    quantize(bgr, pixel_count, packed, lut, true);
}
