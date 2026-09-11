/* SPDX-License-Identifier: MIT */
#include "display/papercolor_reference_chart.h"
#include "sdkconfig.h"

#if defined(CONFIG_PAPERCOLOR_REFERENCE_CHART_ON_BOOT) && CONFIG_PAPERCOLOR_REFERENCE_CHART_ON_BOOT
#include <M5Unified.h>
#include "display/display_metrics.h"
#include "display/papercolor_lut_display.h"
#include "esp_log.h"

extern const uint8_t chart_start[] asm("_binary_papercolor_calibration_v1_png_start");
extern const uint8_t chart_end[] asm("_binary_papercolor_calibration_v1_png_end");

bool papercolor_show_reference_chart()
{
    DisplayMetricsTrace metrics("reference_chart");
    if (M5.Display.width() != 600 || M5.Display.height() != 400) return false;

    // Same backing orientation and RGB565 decoder as the accepted photo path.
    // Use a private Canvas so the test leaves stored photos and UI state intact.
    M5Canvas chart(&M5.Display);
    chart.setPsram(true);
    chart.setColorDepth(16);
    if (!chart.createSprite(600, 400)) return false;
    chart.setRotation(1);
    chart.fillScreen(TFT_WHITE);
    // The canonical PNG is already 400x600: no scaling, cropping or host dither.
    const bool rendered = chart.drawPng(chart_start,
        static_cast<size_t>(chart_end - chart_start),
        0, 0, 0, 0, 0, 0, 1.0f, 1.0f);
    metrics.markRendered();
    if (!rendered) {
        ESP_LOGE("ReferenceChart", "Color chart PNG decode failed; returning to home");
        return false;
    }
    metrics.markRefreshStarted();
    papercolor_push_canvas(&chart, 0, 0, PaperColorRenderMode::PhotoBalanced);
    metrics.finish(true);
    ESP_LOGI("ReferenceChart", "v1 source chart; RGB565 400x600; PhotoBalanced; A returns home");
    return true;
}
#else
bool papercolor_show_reference_chart() { return false; }
#endif
