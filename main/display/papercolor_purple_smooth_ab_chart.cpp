/* SPDX-License-Identifier: MIT */
#include "display/papercolor_purple_smooth_ab_chart.h"
#include "sdkconfig.h"

#if defined(CONFIG_PAPERCOLOR_PURPLE_SMOOTH_AB_CHART_ON_BOOT) && CONFIG_PAPERCOLOR_PURPLE_SMOOTH_AB_CHART_ON_BOOT
#include <M5Unified.h>
#include <array>
#include "display/display_metrics.h"
#include "esp_log.h"

extern const uint8_t purple_smooth_ab_start[] asm("_binary_purple_smooth_ab_v1_bin_start");
extern const uint8_t purple_smooth_ab_end[] asm("_binary_purple_smooth_ab_v1_bin_end");

bool papercolor_show_purple_smooth_ab_chart()
{
    using namespace papercolor_purple_smooth_ab_chart;
    if (M5.Display.width()!=600 || M5.Display.height()!=400) return false;
    const size_t size=static_cast<size_t>(purple_smooth_ab_end-purple_smooth_ab_start);
    if (!valid_payload(purple_smooth_ab_start,size)) {
        ESP_LOGE("PurpleSmoothAB","Invalid pre-rendered payload");
        return false;
    }
    DisplayMetricsTrace metrics("purple_smooth_ab_chart");
    M5Canvas labels(&M5.Display);
    labels.setPsram(true);
    labels.setColorDepth(1);
    if (!labels.createSprite(WIDTH,HEIGHT)) return false;
    labels.setPaletteColor(0,0,0,0);
    labels.setPaletteColor(1,255,255,255);
    labels.fillScreen(TFT_WHITE);
    labels.setTextColor(TFT_BLACK,TFT_WHITE);
    labels.setTextSize(2);
    labels.drawString("PURPLE TRANSITION A/B",12,8);
    labels.setTextSize(1);
    labels.drawString("v1  A: OLD STEP  B: SMOOTH",12,30);
    constexpr const char* solids[]={"BLACK","WHITE","YELLOW","RED","BLUE","GREEN"};
    for (int i=0;i<6;++i) {
        labels.drawString(solids[i],12+i*64,42);
        labels.drawRect(11+i*64,51,58,22,TFT_BLACK);
    }
    for (int col=0;col<4;++col)
        labels.drawString(VARIANTS[col]==0 ? "A" : "B",COLUMN_X+col*COLUMN_STEP+40,84);
    for (int row=0;row<ROW_COUNT;++row)
        labels.drawString(LABELS[row],12,ROW_Y+row*ROW_STEP-15);
    labels.drawString("A B B A: identical repeats check uneven light",12,552);
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
            sample(lx,ly,purple_smooth_ab_start,size,native);
            const auto& rgb=papercolor_native_chart::RGB[native];
            row[x]=RGBColor(rgb[0],rgb[1],rgb[2]);
        }
        M5.Display.pushImage(0,y,600,1,row.data());
    }
    M5.Display.endWrite();
    M5.Display.setEpdMode(previous_mode);
    M5.Display.setClipRect(cx,cy,cw,ch);
    metrics.finish(true);
    ESP_LOGI("PurpleSmoothAB","v1: PhotoBalanced native crops; A legacy / B smooth purple activation; two stimulus ramps and four canonical controls");
    return true;
}
#else
bool papercolor_show_purple_smooth_ab_chart() { return false; }
#endif
