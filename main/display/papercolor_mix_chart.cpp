/* SPDX-License-Identifier: MIT */
#include "display/papercolor_mix_chart.h"
#include "sdkconfig.h"

#if defined(CONFIG_PAPERCOLOR_MIX_RATIO_CHART_ON_BOOT) && CONFIG_PAPERCOLOR_MIX_RATIO_CHART_ON_BOOT
#include <M5Unified.h>
#include <array>
#include "display/display_metrics.h"
#include "esp_log.h"

bool papercolor_show_mix_chart()
{
    using namespace papercolor_mix_chart;
    if (M5.Display.width() != 600 || M5.Display.height() != 400) return false;
    DisplayMetricsTrace metrics("mix_ratio_chart");
    M5Canvas labels(&M5.Display);
    labels.setPsram(true);
    labels.setColorDepth(1);
    if (!labels.createSprite(WIDTH, HEIGHT)) return false;
    labels.setPaletteColor(0, 0, 0, 0);
    labels.setPaletteColor(1, 255, 255, 255);
    labels.fillScreen(TFT_WHITE);
    labels.setTextColor(TFT_BLACK, TFT_WHITE);
    labels.setTextSize(2);
    labels.drawString("MIX RATIO CHECK", 12, 10);
    labels.setTextSize(1);
    labels.drawString("v1 / SAME-SCREEN COLOR AND WHITE COMPARISON", 12, 32);
    constexpr const char* solids[] = {"BLACK","WHITE","YELLOW","RED","BLUE","GREEN"};
    for (int i = 0; i < 6; ++i) {
        labels.drawString(solids[i], 12+i*64, 44);
        labels.drawRect(11+i*64, 53, 58, 26, TFT_BLACK);
    }
    for (int panel = 0; panel < 2; ++panel) {
        const int top = PANEL_Y[panel];
        labels.drawString(panel == 0 ? "A / RED + BLUE : MAGENTA / PURPLE" :
                                      "B / GREEN + BLUE : CYAN / TEAL", 12, top-32);
        labels.drawString(panel == 0 ? "R:" : "G:", 4, top-16);
        for (int col = 0; col < 5; ++col)
            labels.drawString(COLUMN_LABELS[col], COLUMN_X+col*COLUMN_STEP, top-16);
        for (int row = 0; row < 4; ++row) {
            labels.drawString(WHITE_LABELS[row], 4, top+row*ROW_STEP+12);
            for (int col = 0; col < 5; ++col)
                labels.drawRect(COLUMN_X+col*COLUMN_STEP-1, top+row*ROW_STEP-1,
                                PATCH_WIDTH+2, PATCH_HEIGHT+2, TFT_BLACK);
        }
    }
    labels.drawString("ROWS: white share of ALL pixels", 12, 530);
    labels.drawString("COLS: red/green share of COLORED pixels", 12, 544);
    labels.drawString("Compare hue, brightness and visible grain.", 12, 558);
    labels.drawString("Photograph whole chart in even light.", 12, 572);
    labels.drawString("A: return home", 12, 586);
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
            const int lx = y, ly = 599-x;
            uint8_t native = labels.readPixel(lx, ly) == TFT_BLACK ? 0 : 1;
            sample(lx, ly, native);
            const auto& rgb = papercolor_native_chart::RGB[native];
            row[x] = RGBColor(rgb[0],rgb[1],rgb[2]);
        }
        M5.Display.pushImage(0,y,600,1,row.data());
    }
    // Keep exact native-color transfer active through the hardware refresh.
    M5.Display.endWrite();
    M5.Display.setEpdMode(previous_mode);
    M5.Display.setClipRect(cx,cy,cw,ch);
    metrics.finish(true);
    ESP_LOGI("MixChart", "v1: 40 exact mixtures; W 0/12.5/25/37.5; colored R/G 25/37.5/50/62.5/75");
    return true;
}
#else
bool papercolor_show_mix_chart() { return false; }
#endif
