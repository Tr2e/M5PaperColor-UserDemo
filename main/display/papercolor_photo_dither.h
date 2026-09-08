/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    PAPERCOLOR_DITHER_NEAREST = 0,
    PAPERCOLOR_DITHER_FLOYD_STEINBERG,
    PAPERCOLOR_DITHER_BURKES,
} papercolor_dither_mode_t;

typedef struct {
    size_t width;
    size_t row;
    size_t error_values_per_row;
    papercolor_dither_mode_t mode;
    const uint8_t* lut;
    int32_t* current_error;
    int32_t* next_error;
    // Small direct-mapped cache of gamut-constrained Q4 RGB targets.
    struct {
        uint32_t key;
        int16_t target[3];
    } target_cache[32];
} papercolor_dither_state_t;

/** Workspace required by the selected row-streaming dither mode. */
size_t papercolor_dither_workspace_size(size_t width, papercolor_dither_mode_t mode);

/**
 * Initializes deterministic row-streaming quantization.
 * RGB input and output rows must contain exactly width pixels.
 */
bool papercolor_dither_init(papercolor_dither_state_t* state, size_t width,
                            papercolor_dither_mode_t mode, const uint8_t* lut,
                            void* workspace, size_t workspace_size);

/** Clears accumulated error and restarts serpentine traversal at row zero. */
void papercolor_dither_reset(papercolor_dither_state_t* state);

/** Quantizes one RGB888 row to native ED2208 color codes. */
bool papercolor_dither_process_rgb888_row(papercolor_dither_state_t* state,
                                          const uint8_t* rgb,
                                          uint8_t* native_codes);

/**
 * Quantizes one row from the byte-swapped RGB565 layout used by M5Canvas.
 * Each uint16_t contains the big-endian RGB565 bytes as read by the CPU.
 */
bool papercolor_dither_process_swap565_row(papercolor_dither_state_t* state,
                                           const uint16_t* swap565,
                                           uint8_t* native_codes);

#ifdef __cplusplus
}
#endif
