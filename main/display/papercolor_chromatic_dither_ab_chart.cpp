/* SPDX-License-Identifier: MIT */
#include "display/papercolor_chromatic_dither_ab_chart.h"
#include "sdkconfig.h"
#if defined(CONFIG_PAPERCOLOR_CHROMATIC_DITHER_AB_CHART_ON_BOOT) && CONFIG_PAPERCOLOR_CHROMATIC_DITHER_AB_CHART_ON_BOOT
#include <M5Unified.h>
#include <array>
#include "display/display_metrics.h"
extern const uint8_t chromatic_dither_start[] asm("_binary_chromatic_dither_ab_v1_bin_start");
extern const uint8_t chromatic_dither_end[] asm("_binary_chromatic_dither_ab_v1_bin_end");
bool papercolor_show_chromatic_dither_ab_chart() {
    using namespace papercolor_chromatic_dither_ab_chart;
    if(M5.Display.width()!=600 || M5.Display.height()!=400) return false;
    const size_t size=chromatic_dither_end-chromatic_dither_start;
    if(!valid_payload(chromatic_dither_start,size)) return false;
    DisplayMetricsTrace metrics("chromatic_dither_ab_chart"); M5Canvas labels(&M5.Display);
    labels.setPsram(true); labels.setColorDepth(1); if(!labels.createSprite(WIDTH,HEIGHT)) return false;
    labels.setPaletteColor(0,0,0,0); labels.setPaletteColor(1,255,255,255); labels.fillScreen(TFT_WHITE);
    labels.setTextColor(TFT_BLACK,TFT_WHITE); labels.setTextSize(2); labels.drawString("COLOR DITHER A/B",12,7);
    labels.setTextSize(1); labels.drawString("A: FLOYD-STEINBERG   B: BURKES",12,29);
    constexpr const char* solids[]={"BLACK","WHITE","YELLOW","RED","BLUE","GREEN"};
    for(int i=0;i<6;++i){labels.drawString(solids[i],12+i*64,39);labels.drawRect(11+i*64,47,58,22,TFT_BLACK);}
    for(int c=0;c<4;++c) labels.drawString((c==0||c==3)?"A":"B",COLUMN_X+c*COLUMN_STEP+40,76);
    for(int r=0;r<ROW_COUNT;++r) labels.drawString(LABELS[r],12,ROW_Y+r*ROW_STEP-13);
    labels.drawString("Same targets: compare bands and hue",12,548);
    labels.drawString("Check 20 cyan and 11 lime first",12,562);
    labels.drawString("Keep whole chart visible. A: home",12,578);
    for(int x:{2,392}) for(int y:{2,592}) labels.fillRect(x,y,6,6,TFT_BLACK);
    const auto mode=M5.Display.getEpdMode(); int32_t cx,cy,cw,ch; M5.Display.getClipRect(&cx,&cy,&cw,&ch);
    M5.Display.clearClipRect(); M5.Display.setEpdMode(epd_mode_t::epd_fastest); std::array<RGBColor,600> out{};
    metrics.markRendered(); metrics.markRefreshStarted(); M5.Display.startWrite();
    for(int y=0;y<400;++y){for(int x=0;x<600;++x){const int lx=y,ly=599-x;uint8_t n=labels.readPixel(lx,ly)==TFT_BLACK?0:1;
        sample(lx,ly,chromatic_dither_start,size,n);const auto& rgb=papercolor_native_chart::RGB[n];out[x]=RGBColor(rgb[0],rgb[1],rgb[2]);}
        M5.Display.pushImage(0,y,600,1,out.data());}
    M5.Display.endWrite(); M5.Display.setEpdMode(mode); M5.Display.setClipRect(cx,cy,cw,ch); metrics.finish(true); return true;
}
#else
bool papercolor_show_chromatic_dither_ab_chart(){return false;}
#endif
