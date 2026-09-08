/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "display/papercolor_photo_dither.h"

#include <string.h>

#include "display/papercolor_lut.h"

namespace {

constexpr size_t CHANNELS = 3;
constexpr size_t ERROR_PADDING_PIXELS = 2;
constexpr int32_t LINEAR_MAX = 4095;
constexpr size_t INVERSE_LUT_SIZE = LINEAR_MAX + 1;
constexpr size_t FORWARD_LUT_SIZE = 256;

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

// A deterministic gamma-2 approximation keeps error diffusion in a
// linear-light-like domain without floating point or large lookup tables.
constexpr int32_t srgb_to_linear_q12(uint8_t value)
{
    const int32_t squared = static_cast<int32_t>(value) * value;
    return (squared * LINEAR_MAX + 32512) / 65025;
}

constexpr uint16_t NATIVE_LINEAR[7][CHANNELS] = {
    {srgb_to_linear_q12(0), srgb_to_linear_q12(0), srgb_to_linear_q12(0)},
    {srgb_to_linear_q12(255), srgb_to_linear_q12(255), srgb_to_linear_q12(255)},
    {srgb_to_linear_q12(255), srgb_to_linear_q12(243), srgb_to_linear_q12(56)},
    {srgb_to_linear_q12(191), srgb_to_linear_q12(0), srgb_to_linear_q12(0)},
    {srgb_to_linear_q12(255), srgb_to_linear_q12(255), srgb_to_linear_q12(255)},
    {srgb_to_linear_q12(100), srgb_to_linear_q12(64), srgb_to_linear_q12(255)},
    {srgb_to_linear_q12(67), srgb_to_linear_q12(138), srgb_to_linear_q12(28)},
};

uint8_t inverse_linear_q12(int32_t value)
{
    int32_t low = 0;
    int32_t high = 255;
    while (low < high) {
        const int32_t middle = (low + high) / 2;
        if (srgb_to_linear_q12(static_cast<uint8_t>(middle)) < value) {
            low = middle + 1;
        } else {
            high = middle;
        }
    }
    if (low > 0) {
        const int32_t upper_error = srgb_to_linear_q12(static_cast<uint8_t>(low)) - value;
        const int32_t lower_error = value - srgb_to_linear_q12(static_cast<uint8_t>(low - 1));
        if (lower_error <= upper_error) {
            --low;
        }
    }
    return static_cast<uint8_t>(low);
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
    const uint16_t* srgb_to_linear;

    inline uint16_t linear(size_t x, size_t channel) const
    {
        return srgb_to_linear[pixels[x * CHANNELS + channel]];
    }
};

struct Swap565Source {
    const uint16_t* pixels;
    const uint16_t* srgb_to_linear;

    inline uint16_t linear(size_t x, size_t channel) const
    {
        const uint16_t raw = pixels[x];
        uint8_t srgb = 0;
        if (channel == 0) {
            const uint8_t red5 = static_cast<uint8_t>((raw >> 3) & 0x1f);
            srgb = static_cast<uint8_t>((red5 << 3) | (red5 >> 2));
        } else if (channel == 1) {
            const uint8_t green6 = static_cast<uint8_t>(((raw & 0x7) << 3) |
                                                        (raw >> 13));
            srgb = static_cast<uint8_t>((green6 << 2) | (green6 >> 4));
        } else {
            const uint8_t blue5 = static_cast<uint8_t>((raw >> 8) & 0x1f);
            srgb = static_cast<uint8_t>((blue5 << 3) | (blue5 >> 2));
        }
        return srgb_to_linear[srgb];
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
        int32_t adjusted[CHANNELS]{};
        uint8_t lut5[CHANNELS]{};
        for (size_t channel = 0; channel < CHANNELS; ++channel) {
            adjusted[channel] = clamp_i32(
                source.linear(pixel, channel) +
                    signed_shift_round(
                        state->current_error[error_index(pixel, channel)],
                        error_shift),
                0, LINEAR_MAX);
            lut5[channel] = state->linear_to_lut5[adjusted[channel]];
        }

        const size_t lut_index = (static_cast<size_t>(lut5[0]) << 10U) |
                                 (static_cast<size_t>(lut5[1]) << 5U) |
                                 static_cast<size_t>(lut5[2]);
        const uint8_t native = state->lut[lut_index];
        native_codes[pixel] = native;

        const size_t native_index = native <= PAPERCOLOR_NATIVE_GREEN
                                        ? static_cast<size_t>(native)
                                        : static_cast<size_t>(PAPERCOLOR_NATIVE_WHITE);
        if (burkes) {
            for (size_t channel = 0; channel < CHANNELS; ++channel) {
                diffuse_burkes(state, pixel, direction, channel,
                               adjusted[channel] - NATIVE_LINEAR[native_index][channel]);
            }
        } else {
            for (size_t channel = 0; channel < CHANNELS; ++channel) {
                diffuse_floyd_steinberg(
                    state, pixel, direction, channel,
                    adjusted[channel] - NATIVE_LINEAR[native_index][channel]);
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
    constexpr size_t transfer_tables_size = INVERSE_LUT_SIZE +
                                            FORWARD_LUT_SIZE * sizeof(uint16_t);
    if (values_per_row > (SIZE_MAX - transfer_tables_size) / (sizeof(int32_t) * 2)) {
        return 0;
    }
    return values_per_row * sizeof(int32_t) * 2 + transfer_tables_size;
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
        state->linear_to_lut5 = reinterpret_cast<uint8_t*>(
            state->next_error + state->error_values_per_row);
        state->srgb_to_linear = reinterpret_cast<uint16_t*>(
            state->linear_to_lut5 + INVERSE_LUT_SIZE);

        for (int32_t linear = 0; linear <= LINEAR_MAX; ++linear) {
            state->linear_to_lut5[linear] =
                static_cast<uint8_t>(inverse_linear_q12(linear) >> 3);
        }
        for (size_t srgb = 0; srgb < FORWARD_LUT_SIZE; ++srgb) {
            state->srgb_to_linear[srgb] =
                static_cast<uint16_t>(srgb_to_linear_q12(static_cast<uint8_t>(srgb)));
        }
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
        state, Rgb888Source{rgb, state->srgb_to_linear}, native_codes);
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
        state, Swap565Source{swap565, state->srgb_to_linear}, native_codes);
}
