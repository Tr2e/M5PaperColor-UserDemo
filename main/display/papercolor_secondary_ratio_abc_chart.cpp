/* SPDX-License-Identifier: MIT */
#include "display/papercolor_secondary_ratio_abc_chart.h"
#include "sdkconfig.h"

#if defined(CONFIG_PAPERCOLOR_SECONDARY_RATIO_ABC_CHART_ON_BOOT) && CONFIG_PAPERCOLOR_SECONDARY_RATIO_ABC_CHART_ON_BOOT
#include <M5Unified.h>
#include <array>
#include "display/display_metrics.h"
#include "esp_log.h"

extern const uint8_t secondary_ratio_abc_start[] asm("_binary_secondary_ratio_abc_v1_bin_start");
extern const uint8_t secondary_ratio_abc_end[] asm("_binary_secondary_ratio_abc_v1_bin_end");

bool papercolor_show_secondary_ratio_abc_chart()
{
    using namespace papercolor_secondary_ratio_abc_chart;
    if (M5.Display.width()!=600 || M5.Display.height()!=400) return false;
    const size_t size=static_cast<size_t>(secondary_ratio_abc_end-secondary_ratio_abc_start);
    if (!valid_payload(secondary_ratio_abc_start,size)) {
        ESP_LOGE("SecondaryRatioABC","Invalid pre-rendered payload");
        return false;
    }
    DisplayMetricsTrace metrics("secondary_ratio_abc_chart");
    M5Canvas labels(&M5.Display);
    labels.setPsram(true);
    labels.setColorDepth(1);
    if (!labels.createSprite(WIDTH,HEIGHT)) return false;
    labels.setPaletteColor(0,0,0,0);
    labels.setPaletteColor(1,255,255,255);
    labels.fillScreen(TFT_WHITE);
    labels.setTextColor(TFT_BLACK,TFT_WHITE);
    labels.setTextSize(2);
    labels.drawString("SECONDARY RATIO A/B/C",12,8);
    labels.setTextSize(1);
    labels.drawString("A: NOW  B: LESS R/G  C: MORE R/G",12,30);
    constexpr const char* solids[]={"BLACK","WHITE","YELLOW","RED","BLUE","GREEN"};
    for (int i=0;i<6;++i) {
        labels.drawString(solids[i],12+i*64,42);
        labels.drawRect(11+i*64,51,58,22,TFT_BLACK);
    }
    for (int col=0;col<4;++col)
        labels.drawString(VARIANTS[col]==0 ? "A" : (VARIANTS[col]==1 ? "B" : "C"),COLUMN_X+col*COLUMN_STEP+40,84);
    for (int row=0;row<ROW_COUNT;++row)
        labels.drawString(LABELS[row],12,ROW_Y+row*ROW_STEP-15);
    labels.drawString("A B C A: white target fixed; A repeats",12,552);
    labels.drawString("Compare hue, brightness and grain in each row",12,566);
    labels.drawString("Keep whole chart visible. Button A: home",12,582);
    for (int x : {2,392}) for (int y : {2,592}) labels.fillRect(x,y,6,6,TFT_BLACK);

    const auto previous_mode=M5.Display.getEpdMode();
    int32_t cx,cy,cw,ch;
    M5.Display.getClipRect(&cx,&cy,&cw,&ch);
    M5.Display.clearClipRect();
    M5.Display.setEpdMode(epd_mode_t::epd_fastest);
    std::array<RGBColor,600> row{};
    metrics.markRendered();
    metrics.markRefreshStarted();
    M5.Display.startWrite();
    for (int y=0;y<400;++y) {
        for (int x=0;x<600;++x) {
            const int lx=y, ly=599-x;
            uint8_t native=labels.readPixel(lx,ly)==TFT_BLACK ? 0 : 1;
            sample(lx,ly,secondary_ratio_abc_start,size,native);
            const auto& rgb=papercolor_native_chart::RGB[native];
            row[x]=RGBColor(rgb[0],rgb[1],rgb[2]);
        }
        M5.Display.pushImage(0,y,600,1,row.data());
    }
    M5.Display.endWrite();
    M5.Display.setEpdMode(previous_mode);
    M5.Display.setClipRect(cx,cy,cw,ch);
    metrics.finish(true);
    ESP_LOGI("SecondaryRatioABC","v1: host-only secondary ratio brackets at fixed white target; A current, B -6.25pp, C +6.25pp; production photo mapping unchanged");
    return true;
}
#else
bool papercolor_show_secondary_ratio_abc_chart() { return false; }
#endif
