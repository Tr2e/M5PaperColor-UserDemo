// SPDX-License-Identifier: MIT
#include "photo_effect_controller.h"

#include <algorithm>
#include <atomic>
#include <cstring>

#include <M5Unified.h>
#include <esp_heap_caps.h>
#include <esp_log.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "apps/app_manager/app_manager.h"
#include "apps/photo_effects/photo_frame_geometry.h"
#include "display/display_metrics.h"
#include "display/papercolor_oil_painter.h"
#include "hal/hal.h"

namespace {

constexpr const char* kTag = "OilPhoto";

struct FrameState {
    bool valid = false;
    bool oil = false;
    uint32_t generation = 0;
    PaperColorPhotoSource source = PaperColorPhotoSource::Local;
    uint8_t rotation = 0;
    int width = 0;
    int height = 0;
    PaperColorOilRect rect{};
    uint16_t* original = nullptr;
    size_t original_bytes = 0;
};

FrameState g_frame;
std::atomic_bool g_busy{false};

void cooperate(void*)
{
    vTaskDelay(pdMS_TO_TICKS(1));
}

bool canvas_layout(int* width, int* height, uint16_t** pixels, size_t* bytes)
{
    if (!hal.Canvas || hal.Canvas->getColorDepth() != m5gfx::rgb565_2Byte ||
        !hal.Canvas->getBuffer()) return false;
    const uint8_t rotation = hal.Canvas->getRotation() & 3U;
    const int logical_w = hal.Canvas->width();
    const int logical_h = hal.Canvas->height();
    const int backing_w = rotation & 1U ? logical_h : logical_w;
    const int backing_h = rotation & 1U ? logical_w : logical_h;
    if (backing_w <= 0 || backing_h <= 0 || backing_w > 600 || backing_h > 600) return false;
    const size_t required = static_cast<size_t>(backing_w) * backing_h * sizeof(uint16_t);
    if (hal.Canvas->bufferLength() < required) return false;
    *width = backing_w;
    *height = backing_h;
    *pixels = static_cast<uint16_t*>(hal.Canvas->getBuffer());
    *bytes = required;
    return true;
}

void free_original()
{
    if (g_frame.original) heap_caps_free(g_frame.original);
    g_frame.original = nullptr;
    g_frame.original_bytes = 0;
    g_frame.oil = false;
}

}  // namespace

void papercolor_photo_effect_invalidate()
{
    free_original();
    g_frame.valid = false;
    ++g_frame.generation;
}

void papercolor_photo_effect_register(PaperColorPhotoSource source,
                                      int draw_x, int draw_y,
                                      int draw_width, int draw_height)
{
    papercolor_photo_effect_invalidate();
    int backing_w = 0, backing_h = 0;
    uint16_t* pixels = nullptr;
    size_t bytes = 0;
    if (!canvas_layout(&backing_w, &backing_h, &pixels, &bytes)) return;
    (void)pixels;
    (void)bytes;

    const uint8_t rotation = hal.Canvas->getRotation() & 3U;
    const int logical_w = hal.Canvas->width();
    const int logical_h = hal.Canvas->height();
    g_frame.source = source;
    g_frame.rotation = rotation;
    g_frame.width = backing_w;
    g_frame.height = backing_h;
    g_frame.valid = papercolor_photo_backing_rect(logical_w, logical_h, rotation,
        {draw_x, draw_y, draw_width, draw_height}, &g_frame.rect);
}

bool papercolor_photo_effect_is_busy()
{
    return g_busy.load(std::memory_order_acquire);
}

bool papercolor_photo_effect_try_claim_canvas()
{
    bool expected = false;
    return g_busy.compare_exchange_strong(expected, true, std::memory_order_acq_rel);
}

void papercolor_photo_effect_release_canvas()
{
    g_busy.store(false, std::memory_order_release);
}

PaperColorPhotoTarget papercolor_photo_effect_capture_target()
{
    if (!papercolor_photo_effect_try_claim_canvas()) return {};
    const PaperColorPhotoTarget target{g_frame.generation, g_frame.valid};
    papercolor_photo_effect_release_canvas();
    return target;
}

bool papercolor_photo_effect_toggle(PaperColorPhotoTarget target)
{
    if (!papercolor_photo_effect_try_claim_canvas()) return false;
    const auto finish = [](bool result) {
        papercolor_photo_effect_release_canvas();
        return result;
    };

    int backing_w = 0, backing_h = 0;
    uint16_t* canvas_pixels = nullptr;
    size_t frame_bytes = 0;
    if (!target.valid || !g_frame.valid || target.generation != g_frame.generation ||
        !canvas_layout(&backing_w, &backing_h, &canvas_pixels, &frame_bytes) ||
        backing_w != g_frame.width || backing_h != g_frame.height ||
        (hal.Canvas->getRotation() & 3U) != g_frame.rotation) return finish(false);

    DisplayMetricsTrace metrics("oil_photo");
    if (g_frame.oil) {
        if (!g_frame.original || g_frame.original_bytes != frame_bytes) return finish(false);
        std::memcpy(canvas_pixels, g_frame.original, frame_bytes);
        free_original();
        ESP_LOGI(kTag, "Restored original frame generation=%u", static_cast<unsigned>(g_frame.generation));
    } else {
        const size_t workspace_bytes = papercolor_oil_workspace_size(
            g_frame.rect.width, g_frame.rect.height);
        if (!workspace_bytes) return finish(false);
        uint16_t* snapshot = static_cast<uint16_t*>(heap_caps_malloc(
            frame_bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
        void* workspace = heap_caps_malloc(workspace_bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (!snapshot || !workspace) {
            if (snapshot) heap_caps_free(snapshot);
            if (workspace) heap_caps_free(workspace);
            ESP_LOGW(kTag, "PSRAM allocation failed: frame=%u workspace=%u",
                     static_cast<unsigned>(frame_bytes), static_cast<unsigned>(workspace_bytes));
            return finish(false);
        }
        std::memcpy(snapshot, canvas_pixels, frame_bytes);
        PaperColorOilOptions options{};
        options.cooperate = cooperate;
        PaperColorOilStats stats{};
        const uint64_t started_us = static_cast<uint64_t>(esp_timer_get_time());
        const bool rendered = papercolor_oil_render_swap565(
            snapshot, canvas_pixels, backing_w, backing_h, backing_w,
            g_frame.rect, options, workspace, workspace_bytes, &stats);
        heap_caps_free(workspace);
        if (!rendered) {
            std::memcpy(canvas_pixels, snapshot, frame_bytes);
            heap_caps_free(snapshot);
            ESP_LOGE(kTag, "Oil render failed; original Canvas restored");
            return finish(false);
        }
        g_frame.original = snapshot;
        g_frame.original_bytes = frame_bytes;
        g_frame.oil = true;
        ESP_LOGI(kTag, "Oil render generation=%u compute_us=%llu strokes=%u/%u/%u workspace=%u",
                 static_cast<unsigned>(g_frame.generation),
                 static_cast<unsigned long long>(esp_timer_get_time() - started_us),
                 static_cast<unsigned>(stats.coarse_strokes),
                 static_cast<unsigned>(stats.medium_strokes),
                 static_cast<unsigned>(stats.detail_strokes),
                 static_cast<unsigned>(stats.workspace_bytes));
    }

    metrics.markRendered();
    hal.statusEventSend(OPERATION_EVENT_REFRESH_START);
    app_manager_set_refresh_in_progress(true);
    metrics.markRefreshStarted();
    // Production firmware deliberately uses M5GFX's official ED2208 converter.
    hal.Canvas->pushSprite(0, 0);
    app_manager_set_refresh_in_progress(false);
    hal.statusEventSend(OPERATION_EVENT_REFRESH_COMPLETE);
    metrics.finish(true);
    app_manager_mark_activity();
    return finish(true);
}
