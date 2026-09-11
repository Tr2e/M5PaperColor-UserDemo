/* SPDX-License-Identifier: MIT */
#include "display/papercolor_reference_photo.h"
#include "sdkconfig.h"

#if defined(CONFIG_PAPERCOLOR_REFERENCE_PHOTO_ON_BOOT) && CONFIG_PAPERCOLOR_REFERENCE_PHOTO_ON_BOOT
#include <M5Unified.h>
#include "display/display_metrics.h"
#include "display/papercolor_lut_display.h"
#include "esp_log.h"

extern const uint8_t reference_start[] asm("_binary_kodim04_png_start");
extern const uint8_t reference_end[] asm("_binary_kodim04_png_end");

bool papercolor_show_reference_photo()
{
    DisplayMetricsTrace metrics("reference_photo");
    if (M5.Display.width() != 600 || M5.Display.height() != 400) return false;

    // Same RGB565 backing dimensions and portrait rotation as the normal photo
    // path, but no mutation of the global Canvas, selection, filesystem or NVS.
    M5Canvas photo(&M5.Display);
    photo.setPsram(true);
    photo.setColorDepth(16);
    if (!photo.createSprite(600, 400)) return false;
    photo.setRotation(1);
    photo.fillScreen(TFT_WHITE);
    // The unmodified 512x768 PNG has exactly the panel's portrait aspect ratio.
    // Use the same on-device PNG decoder/scaling as local photos, not a second
    // host-side resize or pre-dither. No crop, exposure or color adjustments.
    constexpr float scale = 400.0f / 512.0f;
    const bool rendered = photo.drawPng(reference_start,
        static_cast<size_t>(reference_end - reference_start),
        0, 0, 0, 0, 0, 0, scale, scale);
    metrics.markRendered();
    if (!rendered) {
        ESP_LOGE("ReferencePhoto", "Kodak 04 PNG decode failed; returning to home");
        return false;
    }
    metrics.markRefreshStarted();
    papercolor_push_canvas(&photo, 0, 0, PaperColorRenderMode::PhotoBalanced);
    metrics.finish(true);
    ESP_LOGI("ReferencePhoto", "Kodak 04; RGB565 400x600; PhotoBalanced; A returns home");
    return true;
}
#else
bool papercolor_show_reference_photo() { return false; }
#endif
