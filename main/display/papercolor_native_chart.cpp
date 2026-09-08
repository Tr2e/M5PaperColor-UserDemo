/* SPDX-License-Identifier: MIT */
#include "display/papercolor_native_chart.h"
#include "sdkconfig.h"

#if defined(CONFIG_PAPERCOLOR_NATIVE_CHART_ON_BOOT) && CONFIG_PAPERCOLOR_NATIVE_CHART_ON_BOOT
#include <M5Unified.h>
#include <array>
#include "display/display_metrics.h"
#include "esp_log.h"

bool papercolor_show_native_chart()
{
    using namespace papercolor_native_chart;
    DisplayMetricsTrace metrics("native_chart");
    // Match the production Canvas backing-buffer orientation, without changing
    // the global Canvas, its font/clip state, photo selection, or preferences.
    if (M5.Display.width() != 600 || M5.Display.height() != 400) return false;
    M5Canvas labels(&M5.Display);
    labels.setPsram(true);
    labels.setColorDepth(1);
    if (!labels.createSprite(WIDTH, HEIGHT)) return false;
    labels.setPaletteColor(0, 0, 0, 0);
    labels.setPaletteColor(1, 255, 255, 255);
    labels.fillScreen(TFT_WHITE);
    labels.setTextColor(TFT_BLACK, TFT_WHITE);
    labels.setTextSize(2);
    labels.drawString("NATIVE COLOR REFERENCE", 12, 10);
    labels.setTextSize(1);
    labels.drawString("v1 / DIRECT NATIVE CODES / NO PHOTO LUT OR FS", 12, 32);
    for (int i = 0; i < 6; ++i) {
        labels.drawString(NAMES[i], 12 + (i % 3) * 128, 46 + (i / 3) * 78);
        labels.drawRect(11 + (i % 3) * 128, 57 + (i / 3) * 78, 122, 50, TFT_BLACK);
    }
    labels.drawString("MIXES: SECOND PIGMENT COVERAGE", 12, 194);
    for (int col = 0; col < 5; ++col) {
        char percent[8];
        snprintf(percent, sizeof(percent), "%d%%", col * 25);
        labels.drawString(percent, 12 + col * 76, 206);
    }
    for (int i = 0; i < 6; ++i) {
        labels.drawString(PAIR_NAMES[i], 12, 222 + i * 50);
        for (int col = 0; col < 5; ++col)
            labels.drawRect(11 + col * 76, 233 + i * 50, 74, 34, TFT_BLACK);
    }
    labels.drawString("Fractions are pixel counts, not sRGB values.", 12, 538);
    labels.drawString("Photograph evenly lit, without glare.", 12, 554);
    labels.drawString("Press A to return home. Photos unchanged.", 12, 574);
    labels.fillRect(2, 2, 6, 6, TFT_BLACK);
    labels.fillRect(392, 2, 6, 6, TFT_BLACK);
    labels.fillRect(2, 592, 6, 6, TFT_BLACK);
    labels.fillRect(392, 592, 6, 6, TFT_BLACK);

    const auto previous_mode = M5.Display.getEpdMode();
    int32_t cx, cy, cw, ch;
    M5.Display.getClipRect(&cx, &cy, &cw, &ch);
    M5.Display.clearClipRect();
    M5.Display.setEpdMode(epd_mode_t::epd_fastest);
    std::array<RGBColor, 600> row{};
    metrics.markRendered();
    metrics.markRefreshStarted();
    M5.Display.startWrite();
    for (int y = 0; y < 400; ++y) {
        for (int x = 0; x < 600; ++x) {
            const int lx = y, ly = 599 - x;
            uint8_t code = labels.readPixel(lx, ly) == TFT_BLACK ? 0 : 1;
            sample(lx, ly, code);
            row[x] = RGBColor(RGB[code][0], RGB[code][1], RGB[code][2]);
        }
        M5.Display.pushImage(0, y, 600, 1, row.data());
    }
    // Keep no-dither transfer active until endWrite triggers the panel transfer.
    M5.Display.endWrite();
    M5.Display.setEpdMode(previous_mode);
    M5.Display.setClipRect(cx, cy, cw, ch);
    metrics.finish(true);
    ESP_LOGI("NativeChart", "v1 direct native codes; second-pigment coverage 0/25/50/75/100 percent");
    return true;
}
#else
bool papercolor_show_native_chart() { return false; }
#endif
