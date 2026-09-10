/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#include "papercolor_home.h"

#include <algorithm>
#include <cstdio>

#include <M5Unified.h>
#include "freertos/task.h"

#include "apps/ezdata_photo_push/ezdata_photo_push.h"
#include "apps/local_photo_slideshow/local_photo_slideshow.h"
#include "hal/wifi/hal_wifi.h"
#include "display/papercolor_lut_display.h"

#ifndef APP_ASSETS_USE_EMBEDDED
#define APP_ASSETS_USE_EMBEDDED 0
#endif

#if APP_ASSETS_USE_EMBEDDED
extern const uint8_t _binary_papercolor_web_logo_png_start[] asm("_binary_papercolor_web_logo_png_start");
extern const uint8_t _binary_papercolor_web_logo_png_end[] asm("_binary_papercolor_web_logo_png_end");
#endif

namespace {

constexpr int PHOTO_X = 16;
constexpr int PHOTO_Y = 398;
constexpr int PHOTO_W = 176;
constexpr int PHOTO_H = 145;
constexpr int LOGO_X = 306, LOGO_Y = 7, LOGO_W = 78, LOGO_H = 46;
bool g_home_has_thumbnail = false;

constexpr int GRID_DOT_SIZE = 1;
constexpr int GRID_DOT_STEP = 6;

void use_font(const lgfx::IFont* font, textdatum_t datum = top_left)
{
    hal.Canvas->setFont(font);
    hal.Canvas->setTextSize(1.0f);
    hal.Canvas->setTextDatum(datum);
    hal.Canvas->setTextColor(TFT_BLACK, TFT_WHITE);
}

void dotted_hline(int x, int y, int width)
{
    for (int dx = 0; dx < width; dx += GRID_DOT_STEP) {
        hal.Canvas->fillRect(x + dx, y, std::min(GRID_DOT_SIZE, width - dx), GRID_DOT_SIZE, TFT_BLACK);
    }
}

void dotted_vline(int x, int y, int height)
{
    for (int dy = 0; dy < height; dy += GRID_DOT_STEP) {
        hal.Canvas->fillRect(x, y + dy, GRID_DOT_SIZE, std::min(GRID_DOT_SIZE, height - dy), TFT_BLACK);
    }
}

void dotted_frame(int x, int y, int width, int height)
{
    dotted_hline(x, y, width);
    dotted_hline(x, y + height - GRID_DOT_SIZE, width);
    dotted_vline(x, y, height);
    dotted_vline(x + width - GRID_DOT_SIZE, y, height);
}

int battery_percent(uint16_t battery_mv)
{
    const float voltage = battery_mv / 1000.0f;
    if (voltage >= 4.2f) return 100;
    if (voltage <= 3.2f) return 0;
    if (voltage >= 4.0f) return 85 + static_cast<int>((voltage - 4.0f) * 75.0f);
    if (voltage >= 3.8f) return 50 + static_cast<int>((voltage - 3.8f) * 175.0f);
    if (voltage >= 3.6f) return 15 + static_cast<int>((voltage - 3.6f) * 175.0f);
    if (voltage >= 3.4f) return 5 + static_cast<int>((voltage - 3.4f) * 50.0f);
    return static_cast<int>((voltage - 3.2f) * 25.0f);
}

void draw_battery_gauge(int x, int y, uint16_t battery_mv, bool valid)
{
    constexpr int width  = 29;
    constexpr int height = 13;
    char percent_text[8];
    if (valid) {
        snprintf(percent_text, sizeof(percent_text), "%d%%", battery_percent(battery_mv));
    } else {
        snprintf(percent_text, sizeof(percent_text), "--%%");
    }

    hal.Canvas->drawRoundRect(x, y, width, height, 3, TFT_BLACK);
    hal.Canvas->fillRect(x + width, y + 4, 2, 5, TFT_BLACK);
    if (valid) {
        const int fill_width = (width - 4) * battery_percent(battery_mv) / 100;
        if (fill_width > 0) {
            hal.Canvas->fillRect(x + 2, y + 2, fill_width, height - 4, TFT_BLACK);
        }
    }

    hal.Canvas->setFont(&fonts::lv_font_montserrat_10);
    hal.Canvas->setTextSize(1.0f);
    hal.Canvas->setTextDatum(middle_left);
    hal.Canvas->setTextColor(TFT_BLACK, TFT_WHITE);
    hal.Canvas->drawString(percent_text, x + width + 8, y + height / 2);
    hal.Canvas->setTextDatum(top_left);
}

void draw_date_panel()
{
    static constexpr const char* weekdays[] = {"SUNDAY",   "MONDAY", "TUESDAY", "WEDNESDAY",
                                                "THURSDAY", "FRIDAY", "SATURDAY"};
    m5::rtc_date_t date;
    const bool valid = M5.Rtc.getDate(&date) && date.year >= 2020 && date.year <= 2099 && date.month >= 1 &&
                       date.month <= 12 && date.date >= 1 && date.date <= 31 && date.weekDay >= 0 && date.weekDay <= 6;

    hal.Canvas->fillRect(PAPERCOLOR_HOME_DATE_X, PAPERCOLOR_HOME_DATE_Y, PAPERCOLOR_HOME_DATE_W,
                         PAPERCOLOR_HOME_DATE_H, TFT_WHITE);
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString("RTC / LOCAL DATE", 16, 76);

    char year_text[8];
    if (valid) {
        snprintf(year_text, sizeof(year_text), "%04d", date.year);
    } else {
        snprintf(year_text, sizeof(year_text), "----");
    }
    use_font(&fonts::lv_font_montserrat_14);
    hal.Canvas->drawString(year_text, 16, 99);

    char month_day_text[16];
    if (valid) {
        snprintf(month_day_text, sizeof(month_day_text), "%02d / %02d", date.month, date.date);
    } else {
        snprintf(month_day_text, sizeof(month_day_text), "-- / --");
    }
    use_font(&fonts::lv_font_montserrat_48);
    hal.Canvas->drawString(month_day_text, 12, 117);

    use_font(&fonts::lv_font_montserrat_18);
    hal.Canvas->drawString(valid ? weekdays[date.weekDay] : "DATE NOT SET", 16, 181);
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString(valid ? "SYNC SOURCE / WEB PANEL" : "CONNECT WIFI / SYNC DATE", 16, 217);
}

const char* mode_label(AppMode mode)
{
    switch (mode) {
        case APP_MODE_LOCAL:
            return "LOCAL";
        case APP_MODE_EZDATA:
            return "EZDATA";
        default:
            return "READY";
    }
}

void draw_official_logo(int x, int y)
{
#if APP_ASSETS_USE_EMBEDDED
    // Same stacked PAPER / COLOR wordmark used by the web panel header.
    const uint8_t* data = _binary_papercolor_web_logo_png_start;
    const size_t length = static_cast<size_t>(_binary_papercolor_web_logo_png_end - data);
    hal.Canvas->drawPng(data, length, x, y);
#else
    use_font(&fonts::FreeSansBold12pt7b);
    hal.Canvas->drawString("PAPER COLOR", x, y + 22);
#endif
}

void draw_photo_placeholder()
{
    hal.Canvas->fillRect(PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H, TFT_WHITE);
    dotted_frame(PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H);
    hal.Canvas->fillRect(PHOTO_X + 7, PHOTO_Y + 7, 108, 18, TFT_BLACK);

    hal.Canvas->setTextColor(TFT_WHITE, TFT_BLACK);
    hal.Canvas->setFont(&fonts::lv_font_montserrat_10);
    hal.Canvas->setTextSize(1.0f);
    hal.Canvas->setTextDatum(middle_left);
    hal.Canvas->drawString("IMAGE / EMPTY", PHOTO_X + 12, PHOTO_Y + 16);

    hal.Canvas->setTextColor(TFT_BLACK, TFT_WHITE);
    hal.Canvas->setTextDatum(top_left);
    hal.Canvas->setFont(&fonts::FreeSansBold12pt7b);
    hal.Canvas->drawString("NO IMAGE", PHOTO_X + 10, PHOTO_Y + 34);
    hal.Canvas->setFont(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString("USB / WEB / EZDATA", PHOTO_X + 10, PHOTO_Y + 64);
    hal.Canvas->drawString("B  OPEN LIBRARY", PHOTO_X + 10, PHOTO_Y + 80);

    static constexpr uint8_t bars[] = {2, 5, 2, 3, 7, 2, 4, 2, 6, 3, 2, 5, 2, 7, 3, 2};
    int cursor_x = PHOTO_X + 10;
    for (uint8_t bar : bars) {
        if (cursor_x + bar >= PHOTO_X + PHOTO_W - 10) break;
        hal.Canvas->fillRect(cursor_x, PHOTO_Y + 101, bar, 31, TFT_BLACK);
        cursor_x += bar + 3;
    }
}

void draw_photo_label(uint16_t count, AppMode mode)
{
    char label[40];
    snprintf(label, sizeof(label), "IMAGE / %s / %u", mode_label(mode), (unsigned)count);
    hal.Canvas->setFont(&fonts::lv_font_montserrat_10);
    hal.Canvas->setTextSize(1.0f);
    const int label_width = std::min(PHOTO_W - 16, static_cast<int>(hal.Canvas->textWidth(label)) + 12);
    hal.Canvas->fillRect(PHOTO_X + 7, PHOTO_Y + 7, label_width, 18, TFT_BLACK);
    hal.Canvas->setTextColor(TFT_WHITE, TFT_BLACK);
    hal.Canvas->setTextDatum(middle_left);
    hal.Canvas->drawString(label, PHOTO_X + 12, PHOTO_Y + 16);
    hal.Canvas->setTextDatum(top_left);
    hal.Canvas->setTextColor(TFT_BLACK, TFT_WHITE);
}

void draw_key_row(const char* key, const char* action, int y, int key_width = 24)
{
    hal.Canvas->fillRoundRect(210, y, key_width, 17, 3, TFT_BLACK);
    hal.Canvas->setFont(&fonts::lv_font_montserrat_10);
    hal.Canvas->setTextSize(1.0f);
    hal.Canvas->setTextDatum(middle_center);
    hal.Canvas->setTextColor(TFT_WHITE, TFT_BLACK);
    hal.Canvas->drawString(key, 210 + key_width / 2, y + 8);

    hal.Canvas->setTextDatum(middle_left);
    hal.Canvas->setTextColor(TFT_BLACK, TFT_WHITE);
    hal.Canvas->drawString(action, 210 + key_width + 8, y + 8);
    hal.Canvas->setTextDatum(top_left);
}

void draw_action_cluster(bool audio_muted)
{
    hal.Canvas->fillRect(205, 447, 179, 126, TFT_WHITE);
    draw_key_row("A", "HOLD / CONFIG", 452);
    draw_key_row("B", "OPEN PHOTO", 476);
    draw_key_row("C", audio_muted ? "SOUND ON" : "MUTE AUDIO", 500);
    dotted_hline(210, 531, 174);
    use_font(&fonts::lv_font_montserrat_8);
    hal.Canvas->drawString("AUDIO / STATE", 210, 540);
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString(audio_muted ? "MUTED / PERSISTENT" : "SOUND ON / C TO MUTE", 210, 553);
}

}  // namespace

void papercolor_home_draw_audio_state(bool audio_muted)
{
    draw_action_cluster(audio_muted);
}

void papercolor_home_draw_date(void)
{
    draw_date_panel();
}

bool papercolor_home_draw(AppMode mode, PhotoSlideshow& local_photos, EzdataPhotoPush& ezdata_photos, bool audio_muted)
{
    hal.Canvas->setRotation(1);
    hal.Canvas->clearClipRect();
    hal.Canvas->fillScreen(TFT_WHITE);

    float temperature = 0.0f;
    float humidity    = 0.0f;
    bool sensor_ok    = false;
    // Complete sensor acquisition before composing the single full home-frame
    // refresh. This also gives the shared I2C bus time to settle during boot.
    for (int attempt = 0; attempt < 12 && !sensor_ok; ++attempt) {
        sensor_ok = hal.sht40Read(&temperature, &humidity);
        if (!sensor_ok) vTaskDelay(pdMS_TO_TICKS(25));
    }
    sensor_ok = sensor_ok && temperature >= -40.0f && temperature <= 125.0f && humidity >= 0.0f && humidity <= 100.0f;

    uint16_t battery_mv = 0;
    bool battery_ok = hal.pm1.readVbat(&battery_mv) == M5PM1_OK;

    // Compact status strip: one baseline at the top, official mark at right.
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString("BAT", 16, 15);
    draw_battery_gauge(43, 13, battery_mv, battery_ok);
    hal.Canvas->drawString("HOME / 01", 125, 15);
    hal.Canvas->drawString(mode_label(mode), 202, 15);
    draw_official_logo(LOGO_X, LOGO_Y);
    dotted_hline(16, 60, 368);

    // Hero: RTC-backed calendar date plus a narrow live environment strip.
    draw_date_panel();

    dotted_vline(245, 72, 164);
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString("ENVIRONMENT / LIVE", 260, 76);
    use_font(&fonts::lv_font_montserrat_24);
    char temp_text[20];
    snprintf(temp_text, sizeof(temp_text), sensor_ok ? "%.1f C" : "--.- C", temperature);
    hal.Canvas->drawString(temp_text, 258, 103);
    use_font(&fonts::lv_font_montserrat_18);
    char humidity_text[20];
    snprintf(humidity_text, sizeof(humidity_text), sensor_ok ? "%.0f %% RH" : "-- %% RH", humidity);
    hal.Canvas->drawString(humidity_text, 260, 140);

    if (sensor_ok) {
        hal.Canvas->fillRoundRect(260, 176, 80, 20, 3, TFT_BLACK);
        hal.Canvas->setTextColor(TFT_WHITE, TFT_BLACK);
    } else {
        hal.Canvas->drawRoundRect(260, 176, 80, 20, 3, TFT_BLACK);
        hal.Canvas->setTextColor(TFT_BLACK, TFT_WHITE);
    }
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->setTextDatum(middle_center);
    hal.Canvas->setTextColor(sensor_ok ? TFT_WHITE : TFT_BLACK, sensor_ok ? TFT_BLACK : TFT_WHITE);
    hal.Canvas->drawString(sensor_ok ? "SHT40 / LIVE" : "SHT40 / CHECK", 300, 186);
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString("AMBIENT SENSOR", 260, 213);

    dotted_hline(16, 244, 368);

    // Compact two-column index; modules are grouped by function, not forced
    // into equal dashboard cards.
    use_font(&fonts::lv_font_montserrat_14);
    hal.Canvas->drawString("HARDWARE INDEX", 16, 256);
    use_font(&fonts::lv_font_montserrat_10, top_right);
    hal.Canvas->drawString("04 MODULES", 384, 259);
    dotted_hline(16, 280, 368);
    dotted_vline(198, 289, 86);

    use_font(&fonts::lv_font_montserrat_14);
    hal.Canvas->drawString("01 / DISPLAY", 16, 290);
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString("6-COLOR E-PAPER / 400 x 600", 16, 311);

    use_font(&fonts::lv_font_montserrat_14);
    hal.Canvas->drawString("02 / CONNECT", 210, 290);
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString(hal_wifi::WiFi.isConnected() ? "WIFI / ONLINE / USB MSC" : "WIFI / AP READY / USB MSC", 210,
                           311);

    dotted_hline(16, 337, 169);
    dotted_hline(210, 337, 174);

    use_font(&fonts::lv_font_montserrat_14);
    hal.Canvas->drawString("03 / SENSE", 16, 346);
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString("SHT40 / MIC / BUTTONS", 16, 367);

    use_font(&fonts::lv_font_montserrat_14);
    hal.Canvas->drawString("04 / STORAGE", 210, 346);
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString(hal.isSDCardInserted() ? "TF / INSERTED / INTERNAL" : "TF / EMPTY / INTERNAL", 210, 367);

    dotted_hline(16, 386, 368);

    bool thumbnail_drawn = false;
    uint16_t photo_count = 0;
    if (mode == APP_MODE_EZDATA) {
        photo_count     = ezdata_photos.getTotal();
        thumbnail_drawn = ezdata_photos.drawThumbnail(PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H);
    } else {
        thumbnail_drawn = local_photos.drawThumbnail(PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H);
        photo_count     = local_photos.getTotal();
    }

    if (thumbnail_drawn) {
        dotted_frame(PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H);
        draw_photo_label(photo_count, mode);
    } else {
        draw_photo_placeholder();
    }

    // Unboxed action cluster balances the image tile without turning the
    // lower half into two equal cards.
    use_font(&fonts::lv_font_montserrat_10);
    hal.Canvas->drawString("NEXT / MODULE", 210, 398);
    use_font(&fonts::lv_font_montserrat_18);
    hal.Canvas->drawString("IMAGE VIEW", 210, 414);
    dotted_hline(210, 443, 174);
    draw_action_cluster(audio_muted);

    dotted_hline(16, 576, 368);
    use_font(&fonts::lv_font_montserrat_8);
    hal.Canvas->drawString("M5STACK / PAPER COLOR", 16, 585);
    hal.Canvas->setTextDatum(top_right);
    hal.Canvas->drawString("HOME / READY", 384, 585);
    hal.Canvas->setTextDatum(top_left);

    g_home_has_thumbnail = thumbnail_drawn;
    return thumbnail_drawn;
}

void papercolor_home_push(void)
{
    PaperColorPhotoRegion regions[2]{};
    size_t count = 0;
    if (g_home_has_thumbnail) regions[count++] = {PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H};
#if APP_ASSETS_USE_EMBEDDED
    regions[count++] = {LOGO_X, LOGO_Y, LOGO_W, LOGO_H};
#endif
    papercolor_push_canvas(hal.Canvas, 0, 0, PaperColorRenderMode::UiWithPhotos, regions, count);
}
