/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PAPERCOLOR_LUT_BITS (5U)
#define PAPERCOLOR_LUT_EDGE (1U << PAPERCOLOR_LUT_BITS)
#define PAPERCOLOR_LUT_SIZE (PAPERCOLOR_LUT_EDGE * PAPERCOLOR_LUT_EDGE * PAPERCOLOR_LUT_EDGE)

enum {
    PAPERCOLOR_NATIVE_BLACK  = 0x0,
    PAPERCOLOR_NATIVE_WHITE  = 0x1,
    PAPERCOLOR_NATIVE_YELLOW = 0x2,
    PAPERCOLOR_NATIVE_RED    = 0x3,
    PAPERCOLOR_NATIVE_BLUE   = 0x5,
    PAPERCOLOR_NATIVE_GREEN  = 0x6,
};

/** Returns the 15-bit LUT index for one sRGB color. */
size_t papercolor_lut_index(uint8_t red, uint8_t green, uint8_t blue);

/** Returns one native ED2208 color code from a 32 KiB LUT. */
uint8_t papercolor_lut_lookup(const uint8_t* lut, uint8_t red, uint8_t green, uint8_t blue);

/**
 * Converts packed RGB888 pixels to the ED2208 two-pixels-per-byte layout.
 * An odd final pixel is paired with native white in the low nibble.
 */
void papercolor_quantize_rgb888_4bpp(const uint8_t* rgb, size_t pixel_count, uint8_t* packed,
                                     const uint8_t* lut);

/** Same conversion for M5GFX-style BGR888 input. */
void papercolor_quantize_bgr888_4bpp(const uint8_t* bgr, size_t pixel_count, uint8_t* packed,
                                     const uint8_t* lut);

#ifdef __cplusplus
}
#endif
