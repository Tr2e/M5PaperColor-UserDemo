/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "display/papercolor_photo_dither.h"

#include <string.h>
#ifdef ESP_PLATFORM
#include "sdkconfig.h"
#endif

#include "display/papercolor_lut.h"
#include "display/papercolor_gamut.h"

namespace {

constexpr size_t CHANNELS = 3;
constexpr size_t ERROR_PADDING_PIXELS = 2;
constexpr int32_t RGB_SCALE = 16;
// Numerical safety bound, far outside the normal quantization residual.
constexpr int32_t MAX_RESIDUAL = 4 * 255 * RGB_SCALE;

constexpr uint8_t native_mask(uint8_t native)
{
    return static_cast<uint8_t>(1U << native);
}

constexpr uint8_t NATIVE_CANDIDATES[] = {
    PAPERCOLOR_NATIVE_BLACK, PAPERCOLOR_NATIVE_WHITE,
    PAPERCOLOR_NATIVE_YELLOW, PAPERCOLOR_NATIVE_RED,
    PAPERCOLOR_NATIVE_BLUE, PAPERCOLOR_NATIVE_GREEN,
};
constexpr uint8_t MASK_BLACK_WHITE =
    native_mask(PAPERCOLOR_NATIVE_BLACK) |
    native_mask(PAPERCOLOR_NATIVE_WHITE);
constexpr uint8_t MASK_RED =
    MASK_BLACK_WHITE | native_mask(PAPERCOLOR_NATIVE_RED);
constexpr uint8_t MASK_GREEN =
    MASK_BLACK_WHITE | native_mask(PAPERCOLOR_NATIVE_GREEN);
constexpr uint8_t MASK_BLUE =
    MASK_BLACK_WHITE | native_mask(PAPERCOLOR_NATIVE_BLUE);
constexpr uint8_t MASK_RED_YELLOW =
    MASK_RED | native_mask(PAPERCOLOR_NATIVE_YELLOW);
constexpr uint8_t MASK_RED_BLUE =
    MASK_RED | native_mask(PAPERCOLOR_NATIVE_BLUE);
constexpr uint8_t MASK_GREEN_YELLOW =
    MASK_GREEN | native_mask(PAPERCOLOR_NATIVE_YELLOW);
constexpr uint8_t MASK_GREEN_BLUE =
    MASK_GREEN | native_mask(PAPERCOLOR_NATIVE_BLUE);
constexpr uint8_t MASK_ALL = MASK_RED_YELLOW | MASK_GREEN_BLUE;

inline bool mask_allows(uint8_t mask, uint8_t native)
{
    return native < 8 && (mask & static_cast<uint8_t>(1U << native)) != 0;
}

inline int32_t clamp_i32(int32_t value, int32_t low, int32_t high)
{
    return value < low ? low : (value > high ? high : value);
}

inline int32_t signed_shift_round(int32_t value, uint8_t shift)
{
    const int32_t half = 1 << (shift - 1);
    return value >= 0 ? (value + half) >> shift
                      : -((-value + half) >> shift);
}

constexpr uint8_t NATIVE_SRGB[7][CHANNELS] = {
    {0, 0, 0},
    {255, 255, 255},
    {255, 243, 56},
    {191, 0, 0},
    {255, 255, 255},
    {100, 64, 255},
    {67, 138, 28},
};

// Keep error diffusion from introducing implausible pigment speckles while
// retaining both pigments needed to reproduce secondary hues. Candidate pairs
// follow adjacent sectors of the RGB hue wheel: yellow uses red+yellow, purple
// uses red+blue, cyan uses green+blue, and lime uses green+yellow.
inline uint8_t candidate_mask(uint8_t red, uint8_t green, uint8_t blue)
{
    const uint8_t maximum = red > green ? (red > blue ? red : blue)
                                        : (green > blue ? green : blue);
    const uint8_t minimum = red < green ? (red < blue ? red : blue)
                                        : (green < blue ? green : blue);

    // RGB565 expansion can separate equal source channels by up to seven.
    // Neutral dark/mid tones need the same achromatic guard as highlights.
    if (static_cast<int32_t>(maximum) - minimum <= 8 ||
        (maximum >= 170 && static_cast<int32_t>(maximum) - minimum <= 20)) {
        return MASK_BLACK_WHITE;
    }
    if (static_cast<int32_t>(maximum) - minimum < 24) {
        return MASK_ALL;
    }

    if (red >= green && red >= blue) {
        if (green >= static_cast<int32_t>(blue) + 12) {
            return MASK_RED_YELLOW;
        }
        if (blue >= static_cast<int32_t>(green) + 12) {
            return MASK_RED_BLUE;
        }
        return MASK_RED;
    }
    if (green >= red && green >= blue) {
        if (red >= static_cast<int32_t>(blue) + 12) {
            return MASK_GREEN_YELLOW;
        }
        if (blue >= static_cast<int32_t>(red) + 12) {
            return MASK_GREEN_BLUE;
        }
        return MASK_GREEN;
    }
    if (red >= static_cast<int32_t>(green) + 12) {
        return MASK_RED_BLUE;
    }
    if (green >= static_cast<int32_t>(red) + 12) {
        return MASK_GREEN_BLUE;
    }
    return MASK_BLUE;
}

inline uint8_t nearest_allowed_native_srgb(uint8_t mask,
                                           const int32_t adjusted[CHANNELS])
{
    uint8_t closest = PAPERCOLOR_NATIVE_WHITE;
    uint32_t closest_distance = UINT32_MAX;
    for (uint8_t native : NATIVE_CANDIDATES) {
        if ((mask & native_mask(native)) == 0) {
            continue;
        }
        uint32_t distance = 0;
        for (size_t channel = 0; channel < CHANNELS; ++channel) {
            const int32_t difference =
                adjusted[channel] - NATIVE_SRGB[native][channel] * RGB_SCALE;
            distance += static_cast<uint32_t>(difference * difference);
        }
        if (distance < closest_distance) {
            closest_distance = distance;
            closest = native;
        }
    }
    return closest;
}

// The nominal LUT is deliberately device-independent, while the ED2208 panel's
// blue pigment is visually stronger than red and its light cyan/green mixtures
// can contain too much white. Apply small, sector-local source compensation
// before diffusion instead of changing the shared LUT or UI color rendering.
inline void compensated_photo_target(uint8_t mask,
                                     const uint8_t original[CHANNELS],
                                     int32_t target[CHANNELS])
{
    for (size_t channel = 0; channel < CHANNELS; ++channel) {
        target[channel] = original[channel];
    }

    if (mask == MASK_RED_BLUE && original[2] > original[0] &&
        static_cast<uint16_t>(original[0]) * 2U >= original[2]) {
        const int32_t blue_excess = original[2] - original[0];
        target[0] = clamp_i32(original[0] + blue_excess * 3 / 4, 0, 255);
        target[2] = original[2] - blue_excess / 5;
        return;
    }

    if (mask == MASK_GREEN_BLUE && original[2] > original[1]) {
        target[0] = original[0] * 7 / 8;
        target[1] = original[1] * 7 / 8;
        target[2] = original[2] * 7 / 8;
        return;
    }

    if (mask == MASK_RED_YELLOW && original[2] >= 32 &&
        original[0] >= static_cast<int32_t>(original[1]) + 80) {
        target[0] = original[0] * 7 / 8;
        target[1] = original[1];
        target[2] = original[2] * 3 / 4;
    }
}

inline void reachable_photo_target(papercolor_dither_state_t* state, uint8_t mask,
                                    const uint8_t original[CHANNELS],
                                    int32_t target[CHANNELS])
{
    const uint32_t key = 1U + (static_cast<uint32_t>(original[0]) << 16U) +
                         (static_cast<uint32_t>(original[1]) << 8U) + original[2];
    auto& cached = state->target_cache[(key ^ (key >> 8U) ^ (key >> 16U)) & 31U];
    if (cached.key != key) {
        int32_t source[CHANNELS];
        compensated_photo_target(mask, original, source);
        papercolor_gamut::Point vertices[6];
        size_t count = 0;
        for (uint8_t native : NATIVE_CANDIDATES) {
            if (mask_allows(mask, native)) {
                vertices[count++] = {static_cast<float>(NATIVE_SRGB[native][0]),
                                     static_cast<float>(NATIVE_SRGB[native][1]),
                                     static_cast<float>(NATIVE_SRGB[native][2])};
            }
        }
#if defined(CONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET) && CONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET
        const auto p = papercolor_gamut::project_primary_white_budget(
#else
        const auto p = papercolor_gamut::project(
#endif
            {static_cast<float>(source[0]), static_cast<float>(source[1]),
             static_cast<float>(source[2])}, vertices, count);
        cached.target[0] = static_cast<int16_t>(p.x * RGB_SCALE + 0.5f);
        cached.target[1] = static_cast<int16_t>(p.y * RGB_SCALE + 0.5f);
        cached.target[2] = static_cast<int16_t>(p.z * RGB_SCALE + 0.5f);
        cached.key = key;
    }
    for (size_t channel = 0; channel < CHANNELS; ++channel) {
        target[channel] = cached.target[channel];
    }
}

inline size_t error_index(size_t x, size_t channel)
{
    return (x + ERROR_PADDING_PIXELS) * CHANNELS + channel;
}

inline void diffuse_floyd_steinberg(papercolor_dither_state_t* state, size_t x,
                                    int32_t direction, size_t channel,
                                    int32_t error)
{
    // Two padding pixels on both sides make these writes safe at row edges.
    // Padding is never sampled and is cleared with the row, so avoiding twelve
    // bounds/saturation checks per pixel is bit-identical for visible pixels.
    int32_t* current = state->current_error + error_index(x, channel);
    int32_t* next = state->next_error + error_index(x, channel);
    const ptrdiff_t step = direction * static_cast<ptrdiff_t>(CHANNELS);
    current[step] += error * 7;
    next[-step] += error * 3;
    next[0] += error * 5;
    next[step] += error;
}

inline void diffuse_burkes(papercolor_dither_state_t* state, size_t x,
                    int32_t direction, size_t channel, int32_t error)
{
    int32_t* current = state->current_error + error_index(x, channel);
    int32_t* next = state->next_error + error_index(x, channel);
    const ptrdiff_t step = direction * static_cast<ptrdiff_t>(CHANNELS);
    current[step] += error * 8;
    current[step * 2] += error * 4;
    next[-step * 2] += error * 2;
    next[-step] += error * 4;
    next[0] += error * 8;
    next[step] += error * 4;
    next[step * 2] += error * 2;
}

struct Rgb888Source {
    const uint8_t* pixels;

    inline void sample(size_t x, uint8_t rgb[CHANNELS]) const
    {
        rgb[0] = pixels[x * CHANNELS];
        rgb[1] = pixels[x * CHANNELS + 1];
        rgb[2] = pixels[x * CHANNELS + 2];
    }
};

struct Swap565Source {
    const uint16_t* pixels;

    inline void sample(size_t x, uint8_t rgb[CHANNELS]) const
    {
        const uint16_t raw = pixels[x];
        const uint8_t red5 = static_cast<uint8_t>((raw >> 3) & 0x1f);
        const uint8_t green6 = static_cast<uint8_t>(((raw & 0x7) << 3) |
                                                    (raw >> 13));
        const uint8_t blue5 = static_cast<uint8_t>((raw >> 8) & 0x1f);
        rgb[0] = static_cast<uint8_t>((red5 << 3) | (red5 >> 2));
        rgb[1] = static_cast<uint8_t>((green6 << 2) | (green6 >> 4));
        rgb[2] = static_cast<uint8_t>((blue5 << 3) | (blue5 >> 2));
    }
};

template <typename Source>
bool process_diffused_row(papercolor_dither_state_t* state,
                          const Source& source, uint8_t* native_codes)
{
    const bool burkes = state->mode == PAPERCOLOR_DITHER_BURKES;
    const uint8_t error_shift = burkes ? 5 : 4;
    const int32_t direction = (state->row & 1U) == 0 ? 1 : -1;
    int32_t x = direction > 0 ? 0 : static_cast<int32_t>(state->width - 1);
    const int32_t end = direction > 0 ? static_cast<int32_t>(state->width) : -1;

    for (; x != end; x += direction) {
        const size_t pixel = static_cast<size_t>(x);
        uint8_t original[CHANNELS]{};
        source.sample(pixel, original);
        const uint8_t allowed = candidate_mask(original[0], original[1], original[2]);
        int32_t target[CHANNELS]{};
        reachable_photo_target(state, allowed, original, target);
        int32_t adjusted[CHANNELS]{};
        bool outside_lut = false;
        for (size_t channel = 0; channel < CHANNELS; ++channel) {
            // Preserve signed residuals: clipping here permanently loses the
            // red/green error that should turn saturated blue into mixtures.
            adjusted[channel] =
                target[channel] +
                    signed_shift_round(
                        state->current_error[error_index(pixel, channel)],
                        error_shift);
            outside_lut |= adjusted[channel] < 0 || adjusted[channel] > 255 * RGB_SCALE;
        }

        // The nominal perceptual LUT preserves the lightness of blue/green
        // sectors, especially cyan. Jointly quantize warm/lime sectors and
        // green-dominant teal so chromatic pixels do not become pale from
        // excess white. Retain the LUT for blue-dominant cyan, with the source
        // compensation above controlling its white proportion.
        uint8_t native = PAPERCOLOR_NATIVE_WHITE;
        if (outside_lut || allowed == MASK_RED_YELLOW || allowed == MASK_GREEN_YELLOW ||
            (allowed == MASK_GREEN_BLUE && original[1] >= original[2])) {
            native = nearest_allowed_native_srgb(allowed, adjusted);
        } else {
            const size_t lut_index =
                (static_cast<size_t>(adjusted[0] >> 7) << 10U) |
                (static_cast<size_t>(adjusted[1] >> 7) << 5U) |
                static_cast<size_t>(adjusted[2] >> 7);
            native = state->lut[lut_index];
            if (!mask_allows(allowed, native)) {
                native = nearest_allowed_native_srgb(allowed, adjusted);
            }
        }
        native_codes[pixel] = native;

        const size_t native_index = native <= PAPERCOLOR_NATIVE_GREEN
                                        ? static_cast<size_t>(native)
                                        : static_cast<size_t>(PAPERCOLOR_NATIVE_WHITE);
        if (burkes) {
            for (size_t channel = 0; channel < CHANNELS; ++channel) {
                diffuse_burkes(state, pixel, direction, channel,
                               clamp_i32(adjusted[channel] -
                                             NATIVE_SRGB[native_index][channel] * RGB_SCALE,
                                         -MAX_RESIDUAL, MAX_RESIDUAL));
            }
        } else {
            for (size_t channel = 0; channel < CHANNELS; ++channel) {
                diffuse_floyd_steinberg(
                    state, pixel, direction, channel,
                    clamp_i32(adjusted[channel] -
                                  NATIVE_SRGB[native_index][channel] * RGB_SCALE,
                              -MAX_RESIDUAL, MAX_RESIDUAL));
            }
        }
    }

    memset(state->current_error, 0,
           state->error_values_per_row * sizeof(int32_t));
    int32_t* cleared = state->current_error;
    state->current_error = state->next_error;
    state->next_error = cleared;
    ++state->row;
    return true;
}

}  // namespace

size_t papercolor_dither_workspace_size(size_t width, papercolor_dither_mode_t mode)
{
    if (mode == PAPERCOLOR_DITHER_NEAREST || width == 0) {
        return 0;
    }
    if (width > SIZE_MAX / CHANNELS - ERROR_PADDING_PIXELS * 2) {
        return 0;
    }
    const size_t values_per_row = (width + ERROR_PADDING_PIXELS * 2) * CHANNELS;
    if (values_per_row > SIZE_MAX / (sizeof(int32_t) * 2)) {
        return 0;
    }
    return values_per_row * sizeof(int32_t) * 2;
}

bool papercolor_dither_init(papercolor_dither_state_t* state, size_t width,
                            papercolor_dither_mode_t mode, const uint8_t* lut,
                            void* workspace, size_t workspace_size)
{
    if (!state || !lut || width == 0 || mode < PAPERCOLOR_DITHER_NEAREST ||
        mode > PAPERCOLOR_DITHER_BURKES ||
        width > SIZE_MAX / CHANNELS - ERROR_PADDING_PIXELS * 2) {
        return false;
    }

    memset(state, 0, sizeof(*state));
    state->width = width;
    state->mode = mode;
    state->lut = lut;
    state->error_values_per_row = (width + ERROR_PADDING_PIXELS * 2) * CHANNELS;

    const size_t required = papercolor_dither_workspace_size(width, mode);
    if (required != 0) {
        if (!workspace || workspace_size < required) {
            memset(state, 0, sizeof(*state));
            return false;
        }
        memset(workspace, 0, required);
        state->current_error = static_cast<int32_t*>(workspace);
        state->next_error = state->current_error + state->error_values_per_row;
    }
    return true;
}

void papercolor_dither_reset(papercolor_dither_state_t* state)
{
    if (!state) {
        return;
    }
    state->row = 0;
    if (state->current_error && state->error_values_per_row != 0) {
        memset(state->current_error, 0, state->error_values_per_row * sizeof(int32_t));
        memset(state->next_error, 0, state->error_values_per_row * sizeof(int32_t));
    }
}

bool papercolor_dither_process_rgb888_row(papercolor_dither_state_t* state,
                                          const uint8_t* rgb,
                                          uint8_t* native_codes)
{
    if (!state || !rgb || !native_codes || !state->lut || state->width == 0) {
        return false;
    }

    if (state->mode == PAPERCOLOR_DITHER_NEAREST) {
        for (size_t x = 0; x < state->width; ++x) {
            native_codes[x] = papercolor_lut_lookup(state->lut, rgb[x * 3],
                                                    rgb[x * 3 + 1], rgb[x * 3 + 2]);
        }
        ++state->row;
        return true;
    }

    return process_diffused_row(
        state, Rgb888Source{rgb}, native_codes);
}

bool papercolor_dither_process_swap565_row(papercolor_dither_state_t* state,
                                           const uint16_t* swap565,
                                           uint8_t* native_codes)
{
    if (!state || !swap565 || !native_codes || !state->lut || state->width == 0) {
        return false;
    }

    if (state->mode == PAPERCOLOR_DITHER_NEAREST) {
        for (size_t x = 0; x < state->width; ++x) {
            const uint16_t raw = swap565[x];
            const size_t red5 = (raw >> 3) & 0x1f;
            const size_t green5 = ((((raw & 0x7) << 3) | (raw >> 13)) >> 1) & 0x1f;
            const size_t blue5 = (raw >> 8) & 0x1f;
            native_codes[x] = state->lut[(red5 << 10U) |
                                         (green5 << 5U) | blue5];
        }
        ++state->row;
        return true;
    }

    return process_diffused_row(
        state, Swap565Source{swap565}, native_codes);
}
