/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "display/papercolor_lut_display.h"

#include <M5Unified.h>
#include <freertos/FreeRTOS.h>

#include "display/papercolor_lut.h"

#if defined(CONFIG_PAPERCOLOR_EXPERIMENTAL_LUT) && CONFIG_PAPERCOLOR_EXPERIMENTAL_LUT
#include <array>
#include <esp_heap_caps.h>
#include <esp_timer.h>

#include "display/papercolor_photo_dither.h"

extern const uint8_t _binary_nominal_5bit_lut_start[] asm("_binary_nominal_5bit_lut_start");
extern const uint8_t _binary_nominal_5bit_lut_end[] asm("_binary_nominal_5bit_lut_end");

namespace {

constexpr size_t MAX_ROW_PIXELS = 600;
constexpr size_t INTERNAL_HEAP_RESERVE = 96 * 1024;
constexpr std::array<RGBColor, 7> NATIVE_RGB = {
    RGBColor(0, 0, 0),
    RGBColor(255, 255, 255),
    RGBColor(255, 243, 56),
    RGBColor(191, 0, 0),
    RGBColor(255, 255, 255),
    RGBColor(100, 64, 255),
    RGBColor(67, 138, 28),
};
portMUX_TYPE g_pipeline_stats_mux = portMUX_INITIALIZER_UNLOCKED;
PaperColorPipelineStats g_pipeline_stats{};

void store_pipeline_stats(PaperColorRenderMode mode, uint64_t prepare_us,
                          size_t workspace_bytes)
{
    const PaperColorPipelineStats stats{true, mode, prepare_us, workspace_bytes};
    portENTER_CRITICAL(&g_pipeline_stats_mux);
    g_pipeline_stats = stats;
    portEXIT_CRITICAL(&g_pipeline_stats_mux);
}

}  // namespace
#endif

const char* papercolor_render_mode_name(PaperColorRenderMode mode)
{
    switch (mode) {
        case PaperColorRenderMode::Ui:            return "ui";
        case PaperColorRenderMode::PhotoBalanced: return "photo-balanced";
        case PaperColorRenderMode::PhotoDetail:   return "photo-detail";
        case PaperColorRenderMode::Legacy:        return "legacy";
        default:                                  return "unknown";
    }
}

bool papercolor_pipeline_stats_snapshot(PaperColorPipelineStats* stats)
{
    if (!stats) {
        return false;
    }
#if !defined(CONFIG_PAPERCOLOR_EXPERIMENTAL_LUT) || !CONFIG_PAPERCOLOR_EXPERIMENTAL_LUT
    *stats = {};
    return false;
#else
    portENTER_CRITICAL(&g_pipeline_stats_mux);
    *stats = g_pipeline_stats;
    portEXIT_CRITICAL(&g_pipeline_stats_mux);
    return stats->valid;
#endif
}

void papercolor_push_canvas(m5gfx::M5Canvas* canvas, int32_t x, int32_t y,
                            PaperColorRenderMode mode)
{
    if (!canvas) {
        return;
    }

#if !defined(CONFIG_PAPERCOLOR_EXPERIMENTAL_LUT) || !CONFIG_PAPERCOLOR_EXPERIMENTAL_LUT
    (void)mode;
    canvas->pushSprite(x, y);
#else
    if (mode == PaperColorRenderMode::Legacy) {
        canvas->pushSprite(x, y);
        return;
    }
    const size_t lut_size = static_cast<size_t>(_binary_nominal_5bit_lut_end -
                                                _binary_nominal_5bit_lut_start);
    if (lut_size != PAPERCOLOR_LUT_SIZE) {
        canvas->pushSprite(x, y);
        return;
    }

    // pushSprite uses the unrotated backing buffer. Read in the same coordinate
    // system, then restore the caller's logical Canvas rotation before returning.
    const uint8_t canvas_rotation = canvas->getRotation();
    int32_t clip_x = 0;
    int32_t clip_y = 0;
    int32_t clip_width = 0;
    int32_t clip_height = 0;
    int32_t scroll_x = 0;
    int32_t scroll_y = 0;
    int32_t scroll_width = 0;
    int32_t scroll_height = 0;
    canvas->getClipRect(&clip_x, &clip_y, &clip_width, &clip_height);
    canvas->getScrollRect(&scroll_x, &scroll_y, &scroll_width, &scroll_height);
    const auto restore_canvas_state = [&]() {
        canvas->setRotation(canvas_rotation);
        canvas->setClipRect(clip_x, clip_y, clip_width, clip_height);
        canvas->setScrollRect(scroll_x, scroll_y, scroll_width, scroll_height);
    };
    canvas->setRotation(0);
    const int32_t width = canvas->width();
    const int32_t height = canvas->height();
    if (width <= 0 || height <= 0 || static_cast<size_t>(width) > MAX_ROW_PIXELS) {
        restore_canvas_state();
        canvas->pushSprite(x, y);
        return;
    }

    papercolor_dither_mode_t dither_mode = PAPERCOLOR_DITHER_NEAREST;
    if (mode == PaperColorRenderMode::PhotoBalanced) {
        dither_mode = PAPERCOLOR_DITHER_FLOYD_STEINBERG;
    } else if (mode == PaperColorRenderMode::PhotoDetail) {
        dither_mode = PAPERCOLOR_DITHER_BURKES;
    }

    const uint64_t prepare_started_us = static_cast<uint64_t>(esp_timer_get_time());
    const size_t workspace_size = papercolor_dither_workspace_size(width, dither_mode);
    void* workspace = nullptr;
    if (workspace_size != 0) {
        const size_t internal_free =
            heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
        const size_t internal_largest =
            heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
        if (internal_free >= workspace_size + INTERNAL_HEAP_RESERVE &&
            internal_largest >= workspace_size) {
            workspace = heap_caps_calloc(
                1, workspace_size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
        }
        if (!workspace) {
            workspace = heap_caps_calloc(
                1, workspace_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        }
        if (!workspace) {
            restore_canvas_state();
            canvas->pushSprite(x, y);
            return;
        }
    }

    papercolor_dither_state_t dither{};
    if (!papercolor_dither_init(&dither, width, dither_mode,
                                _binary_nominal_5bit_lut_start, workspace,
                                workspace_size)) {
        if (workspace) {
            heap_caps_free(workspace);
        }
        restore_canvas_state();
        canvas->pushSprite(x, y);
        return;
    }

    std::array<RGBColor, MAX_ROW_PIXELS> row{};
    std::array<uint8_t, MAX_ROW_PIXELS * 3> rgb{};
    std::array<uint8_t, MAX_ROW_PIXELS> native_codes{};
    const size_t source_bytes = static_cast<size_t>(width) *
                                static_cast<size_t>(height) * sizeof(uint16_t);
    const bool use_swap565_fast_path =
        canvas->getColorDepth() == m5gfx::rgb565_2Byte &&
        canvas->getBuffer() != nullptr && canvas->bufferLength() >= source_bytes;
    const uint16_t* source_swap565 = use_swap565_fast_path
                                         ? static_cast<const uint16_t*>(canvas->getBuffer())
                                         : nullptr;
    const epd_mode_t previous_mode = M5.Display.getEpdMode();
    M5.Display.setEpdMode(epd_mode_t::epd_fastest);
    M5.Display.startWrite();
    for (int32_t row_index = 0; row_index < height; ++row_index) {
        if (use_swap565_fast_path) {
            papercolor_dither_process_swap565_row(
                &dither,
                source_swap565 + static_cast<size_t>(row_index) * width,
                native_codes.data());
        } else {
            canvas->readRectRGB(0, row_index, width, 1, row.data());
            for (int32_t column = 0; column < width; ++column) {
                rgb[column * 3] = row[column].r;
                rgb[column * 3 + 1] = row[column].g;
                rgb[column * 3 + 2] = row[column].b;
            }
            papercolor_dither_process_rgb888_row(
                &dither, rgb.data(), native_codes.data());
        }
        for (int32_t column = 0; column < width; ++column) {
            const uint8_t native = native_codes[column];
            const size_t native_index =
                native <= PAPERCOLOR_NATIVE_GREEN
                    ? static_cast<size_t>(native)
                    : static_cast<size_t>(PAPERCOLOR_NATIVE_WHITE);
            row[column] = NATIVE_RGB[native_index];
        }
        M5.Display.pushImage(x, y + row_index, width, 1, row.data());
    }
    const uint64_t prepare_finished_us = static_cast<uint64_t>(esp_timer_get_time());
    store_pipeline_stats(mode, prepare_finished_us - prepare_started_us, workspace_size);
    if (workspace) {
        heap_caps_free(workspace);
        workspace = nullptr;
    }
    M5.Display.endWrite();
    M5.Display.setEpdMode(previous_mode);
    restore_canvas_state();
#endif
}
