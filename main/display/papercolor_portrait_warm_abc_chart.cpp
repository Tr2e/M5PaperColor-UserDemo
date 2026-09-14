/* SPDX-License-Identifier: MIT */
#include "display/papercolor_portrait_warm_abc_chart.h"

#include "sdkconfig.h"

#if defined(CONFIG_PAPERCOLOR_PORTRAIT_WARM_ABC_CHART_ON_BOOT) && \
    CONFIG_PAPERCOLOR_PORTRAIT_WARM_ABC_CHART_ON_BOOT
#include <M5Unified.h>
#include <array>

#include "display/display_metrics.h"
#include "display/papercolor_native_chart.h"

extern const uint8_t portrait_warm_start[]
    asm("_binary_portrait_warm_abca_v2_bin_start");
extern const uint8_t portrait_warm_end[]
    asm("_binary_portrait_warm_abca_v2_bin_end");

bool papercolor_show_portrait_warm_abc_chart()
{
    using namespace papercolor_portrait_warm_abc_chart;
    if (M5.Display.width() != 600 || M5.Display.height() != 400) return false;
    const size_t size = portrait_warm_end - portrait_warm_start;
    if (!valid_payload(portrait_warm_start, size)) return false;
    DisplayMetricsTrace metrics("portrait_warm_abc_chart");
    M5Canvas labels(&M5.Display);
    labels.setPsram(true);
    labels.setColorDepth(1);
    if (!labels.createSprite(WIDTH, HEIGHT)) return false;
    labels.setPaletteColor(0, 0, 0, 0);
    labels.setPaletteColor(1, 255, 255, 255);
    labels.fillScreen(TFT_WHITE);
    labels.setTextColor(TFT_BLACK, TFT_WHITE);
    labels.setTextSize(2);
    labels.drawString("PORTRAIT WARM A/B/C/A", 8, 6);
    labels.setTextSize(1);
    labels.drawString("A NOW    B +RED 1/16    C +RED 1/8", 8, 28);
    labels.drawString("yellow->red; black/white/color total fixed", 8, 42);
    for (int col = 0; col < 4; ++col) {
        const char* label = (col == 0 || col == 3) ? "A" : (col == 1 ? "B" : "C");
        labels.drawString(label, COLUMN_X + col * COLUMN_STEP + 40, 58);
    }
    for (int row = 0; row < ROW_COUNT; ++row) {
        labels.drawString(LABELS[row], 8, ROW_Y + row * ROW_STEP - 11);
    }
    labels.drawString("Compare skin cast; guard teeth/hat/fabric", 8, 568);
    labels.drawString("Keep full panel visible. Button A: home", 8, 582);

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
            uint8_t native = labels.readPixel(logical_x, logical_y) == TFT_BLACK
                                 ? 0 : 1;
            sample(logical_x, logical_y, portrait_warm_start, size, native);
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
bool papercolor_show_portrait_warm_abc_chart() { return false; }
#endif
