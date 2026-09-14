/* SPDX-License-Identifier: MIT */
#include "display/papercolor_warm_ratio_abc_chart.h"

#include "sdkconfig.h"

#if defined(CONFIG_PAPERCOLOR_WARM_RATIO_ABC_CHART_ON_BOOT) && CONFIG_PAPERCOLOR_WARM_RATIO_ABC_CHART_ON_BOOT
#include <M5Unified.h>
#include <array>
#include "display/display_metrics.h"

extern const uint8_t warm_ratio_start[] asm("_binary_warm_ratio_abc_v1_bin_start");
extern const uint8_t warm_ratio_end[] asm("_binary_warm_ratio_abc_v1_bin_end");

bool papercolor_show_warm_ratio_abc_chart()
{
    using namespace papercolor_warm_ratio_abc_chart;
    if (M5.Display.width() != 600 || M5.Display.height() != 400) return false;
    const size_t size = warm_ratio_end - warm_ratio_start;
    if (!valid_payload(warm_ratio_start, size)) return false;
    DisplayMetricsTrace metrics("warm_ratio_abc_chart");
    M5Canvas labels(&M5.Display);
    labels.setPsram(true);
    labels.setColorDepth(1);
    if (!labels.createSprite(WIDTH, HEIGHT)) return false;
    labels.setPaletteColor(0, 0, 0, 0);
    labels.setPaletteColor(1, 255, 255, 255);
    labels.fillScreen(TFT_WHITE);
    labels.setTextColor(TFT_BLACK, TFT_WHITE);
    labels.setTextSize(2);
    labels.drawString("WARM RATIO A/B/C", 12, 8);
    labels.setTextSize(1);
    labels.drawString("A: NOW   B: +RED   C: -RED", 12, 30);
    constexpr const char* solids[] = {"BLACK", "WHITE", "YELLOW", "RED", "BLUE", "GREEN"};
    for (int i = 0; i < 6; ++i) {
        labels.drawString(solids[i], 12 + i * 64, 42);
        labels.drawRect(11 + i * 64, 51, 58, 22, TFT_BLACK);
    }
    for (int col = 0; col < 4; ++col) {
        const char* label = (col == 0 || col == 3) ? "A" : (col == 1 ? "B" : "C");
        labels.drawString(label, COLUMN_X + col * COLUMN_STEP + 40, 84);
    }
    for (int row = 0; row < ROW_COUNT; ++row) labels.drawString(LABELS[row], 12, ROW_Y + row * ROW_STEP - 15);
    labels.drawString("Rows 14/15: fixed white and color total", 12, 552);
    labels.drawString("Compare hue, brightness, dots and grain", 12, 566);
    labels.drawString("Keep whole chart visible. Button A: home", 12, 582);
    for (int x : {2, 392}) for (int y : {2, 592}) labels.fillRect(x, y, 6, 6, TFT_BLACK);

    const auto mode = M5.Display.getEpdMode();
    int32_t clip_x, clip_y, clip_width, clip_height;
    M5.Display.getClipRect(&clip_x, &clip_y, &clip_width, &clip_height);
    M5.Display.clearClipRect();
    M5.Display.setEpdMode(epd_mode_t::epd_fastest);
    std::array<RGBColor, 600> output{};
    metrics.markRendered();
    metrics.markRefreshStarted();
    M5.Display.startWrite();
    for (int y = 0; y < 400; ++y) {
        for (int x = 0; x < 600; ++x) {
            const int logical_x = y;
            const int logical_y = 599 - x;
            uint8_t native = labels.readPixel(logical_x, logical_y) == TFT_BLACK ? 0 : 1;
            sample(logical_x, logical_y, warm_ratio_start, size, native);
            const auto& rgb = papercolor_native_chart::RGB[native];
            output[x] = RGBColor(rgb[0], rgb[1], rgb[2]);
        }
        M5.Display.pushImage(0, y, 600, 1, output.data());
    }
    M5.Display.endWrite();
    M5.Display.setEpdMode(mode);
    M5.Display.setClipRect(clip_x, clip_y, clip_width, clip_height);
    metrics.finish(true);
    return true;
}
#else
bool papercolor_show_warm_ratio_abc_chart() { return false; }
#endif
