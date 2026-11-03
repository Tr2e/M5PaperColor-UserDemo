#include "calendar_engine.h"
#include "network.h"
#include <M5Unified.h>
#include <M5PM1.h>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

extern const uint8_t pack_start[] asm("_binary_calendar_pack_start");
extern const uint8_t pack_end[] asm("_binary_calendar_pack_end");

namespace {
constexpr const char* TAG="Tr2e";
constexpr uint8_t RTC_ADDR=0x32,RTC_FLAG=0x1d,VLF=0x02;
M5PM1 power;
M5Canvas canvas(&M5.Display);
tr2e::CalendarPack pack;
uint8_t* frame=nullptr;
uint32_t displayed_day=0;
bool state_ok=false;
bool error_visible=false;

void led_off() {M5.Led.setAllColor(0);M5.Led.display();}
void power_hint() {
    power.setLdoEnable(true);
    M5.Led.setBrightness(12);M5.Led.setAllColor(0x303030);M5.Led.display();
    vTaskDelay(pdMS_TO_TICKS(80));led_off();power.setLdoEnable(false);
}
void push() {
    M5.Display.setEpdMode(epd_mode_t::epd_quality);
    canvas.pushSprite(0,0);M5.Display.waitDisplay();
}
void message(const char* title,const char* body,const char* detail=nullptr) {
    if(error_visible) return;
    canvas.setRotation(1);canvas.fillScreen(TFT_WHITE);canvas.setTextColor(TFT_BLACK,TFT_WHITE);
    canvas.setTextDatum(top_left);canvas.setFont(&fonts::efontCN_24_b);canvas.drawString(title,24,150);
    canvas.setFont(&fonts::efontCN_16);canvas.drawString(body,24,210);
    if(detail) canvas.drawString(detail,24,242);
    canvas.drawString("按住 A 键开机可配置网络",24,330);
    canvas.setFont(&fonts::Font2);canvas.drawString("Tr2e",330,555);push();displayed_day=0;error_visible=true;
}
bool read_clock(tr2e::Date& day,m5::rtc_time_t& clock) {
    m5::rtc_date_t date;uint8_t flags=0;
    if(!M5.In_I2C.readRegister(RTC_ADDR,RTC_FLAG,&flags,1,400000) || (flags&VLF) ||
       !M5.Rtc.getDateTime(&date,&clock)) return false;
    day={date.year,date.month,date.date};
    return tr2e::ordinal(day) && date.year>=2026 && date.year<=2099 && clock.hours>=0 && clock.hours<=23 &&
        clock.minutes>=0 && clock.minutes<=59 && clock.seconds>=0 && clock.seconds<=59;
}
bool lock_year(int year) {
    if(!state_ok) return false;
    nvs_handle_t h;if(nvs_open("tr2e",NVS_READWRITE,&h)!=ESP_OK) return false;
    char key[12];snprintf(key,sizeof(key),"p%d",year);uint32_t expected=pack.planHash(year),stored=0;
    auto err=nvs_get_u32(h,key,&stored);bool ok=false;
    if(expected && err==ESP_OK) ok=expected==stored;
    else if(expected && err==ESP_ERR_NVS_NOT_FOUND) ok=nvs_set_u32(h,key,expected)==ESP_OK && nvs_commit(h)==ESP_OK;
    nvs_close(h);return ok;
}
bool show_today() {
    tr2e::Date day{};m5::rtc_time_t time;
    if(!read_clock(day,time)) return false;
    uint32_t key=tr2e::ordinal(day);if(displayed_day==key) return true;
    if(!lock_year(day.year)) {
        message("年度计划需要检查","请保留本年已有的内容计划","升级固件不能重新抽取本年内容");return false;
    }
    if(!pack.render(day,frame,30000)) return false;
    canvas.setRotation(1);canvas.fillScreen(TFT_WHITE);canvas.drawBitmap(0,0,frame,400,600,TFT_BLACK);push();
    displayed_day=key;error_visible=false;tr2e::Entry entry{};pack.entry(day,entry);
    ESP_LOGI(TAG,"Displayed %04d-%02d-%02d source-index=%u",day.year,day.month,day.day,entry.record);
    return true;
}
tr2e::SyncState load_sync() {
    tr2e::SyncState state;nvs_handle_t h;if(nvs_open("tr2e",NVS_READONLY,&h)==ESP_OK) {
        size_t size=sizeof(state);if(nvs_get_blob(h,"sync_state",&state,&size)!=ESP_OK || size!=sizeof(state)) state={};nvs_close(h);
    }return state;
}
bool save_sync(const tr2e::SyncState& state) {
    nvs_handle_t h;if(nvs_open("tr2e",NVS_READWRITE,&h)!=ESP_OK) return false;
    bool ok=nvs_set_blob(h,"sync_state",&state,sizeof(state))==ESP_OK && nvs_commit(h)==ESP_OK;nvs_close(h);return ok;
}
bool set_clock(int64_t utc) {
    // All editorial dates and lunar tables use China standard time. Do not
    // inherit host timezone or apply a second local-time conversion.
    time_t local=static_cast<time_t>(utc+8*3600);tm t{};
    if(!gmtime_r(&local,&t) || t.tm_year+1900<2026 || t.tm_year+1900>2099) return false;
    M5.Rtc.disableIRQ();
    m5::rtc_datetime_t converted{t};auto* rtc=M5.Rtc.getRtcInstancePtr();
    if(!rtc || !rtc->setDateTime(&converted.date,&converted.time)) return false;
    // Epson VLF is bit 1, distinct from the battery-warning bit VBLF (bit 7).
    if(!M5.In_I2C.bitOff(RTC_ADDR,RTC_FLAG,VLF,400000)) return false;
    tr2e::Date d{};m5::rtc_time_t clock;
    return read_clock(d,clock) && d.year==t.tm_year+1900 && d.month==t.tm_mon+1 && d.day==t.tm_mday &&
        clock.hours==t.tm_hour && clock.minutes==t.tm_min;
}
bool setup_requested(tr2e::Boot boot) {
    if(boot!=tr2e::Boot::Manual) return false;
    M5.update();if(!M5.BtnA.isPressed()) return false;
    // A is a display button, separate from the power button; deliberate hold
    // only. No idle scan or automatically opened AP.
    for(int i=0;i<20;++i) {vTaskDelay(pdMS_TO_TICKS(50));M5.update();if(!M5.BtnA.isPressed()) return false;}
    return true;
}
void configure() {
    char ssid[33],pass[16];if(!calendar_setup_start(ssid,sizeof(ssid),pass,sizeof(pass))) return;
    canvas.setRotation(1);canvas.fillScreen(TFT_WHITE);canvas.setTextColor(TFT_BLACK,TFT_WHITE);canvas.setTextDatum(top_left);
    canvas.setFont(&fonts::efontCN_24_b);canvas.drawString("连接此网络配置日历",24,110);
    canvas.setFont(&fonts::Font2);canvas.drawString(ssid,24,170);canvas.drawString(pass,24,210);canvas.drawString("http://192.168.4.1",24,270);
    canvas.setFont(&fonts::efontCN_16);canvas.drawString("上行为网络名称，下行为密码",24,320);canvas.drawString("3分钟后自动关闭",24,355);push();displayed_day=0;error_visible=false;
    int64_t deadline=esp_timer_get_time()+180000000;
    while(esp_timer_get_time()<deadline && !calendar_setup_saved()) vTaskDelay(pdMS_TO_TICKS(100));
    vTaskDelay(pdMS_TO_TICKS(250));calendar_setup_stop();
}
[[noreturn]] void sleep_until_midnight(bool manual) {
    tr2e::Date day{};m5::rtc_time_t time;bool valid=read_clock(day,time);
    if(valid && displayed_day && displayed_day!=tr2e::ordinal(day)) {
        show_today();valid=read_clock(day,time);
    }
    // Do not power off into an alarm that can fire while the cutoff is still
    // in progress. Let midnight pass, redraw, then arm the following midnight.
    if(valid && tr2e::secondsUntilMidnight(time.hours,time.minutes,time.seconds)<=10) {
        const uint32_t previous_day=tr2e::ordinal(day);
        vTaskDelay(pdMS_TO_TICKS((tr2e::secondsUntilMidnight(time.hours,time.minutes,time.seconds)+1)*1000));
        if(frame && state_ok) show_today();
        valid=read_clock(day,time) && tr2e::ordinal(day)>previous_day;
        // A stalled RTC must not recurse, wake in a tight loop, or consume the
        // battery waiting forever. The invalid-clock fallback is one day.
    }
    uint32_t seconds=valid?tr2e::secondsUntilMidnight(time.hours,time.minutes,time.seconds):86400;
    // Match the next calendar day, not an interval rounded from the boot time.
    // A day-specific match also avoids an immediate repeat during 00:00.
    bool armed=false;
    if(valid) {
        tm next{};next.tm_year=day.year-1900;next.tm_mon=day.month-1;next.tm_mday=day.day+1;
        // mktime uses an explicitly fixed UTC TZ only for calendar normalization.
        if(mktime(&next)!=time_t(-1)) {
            M5.Rtc.disableIRQ();M5.Rtc.clearIRQ();
            armed=M5.Rtc.setAlarmIRQ(&next)>0;
            // Library setter does not propagate I2C write failures; verify.
            uint8_t regs[3]{},control=0,extension=0;
            uint8_t bcd=uint8_t((next.tm_mday/10)*16+next.tm_mday%10);
            armed=armed && M5.In_I2C.readRegister(RTC_ADDR,0x17,regs,3,400000) && regs[0]==0 && regs[1]==0 && regs[2]==bcd &&
                M5.In_I2C.readRegister(RTC_ADDR,0x1e,&control,1,400000) && (control&0x08) &&
                M5.In_I2C.readRegister(RTC_ADDR,0x1c,&extension,1,400000) && (extension&0x08);
        }
    }
    bool wake_pin=power.gpioSetFunc(M5PM1_GPIO_NUM_2,M5PM1_GPIO_FUNC_WAKE)==M5PM1_OK &&
        power.gpioSetPull(M5PM1_GPIO_NUM_2,M5PM1_GPIO_PULL_UP)==M5PM1_OK &&
        power.gpioSetWakeEdge(M5PM1_GPIO_NUM_2,M5PM1_GPIO_WAKE_FALLING)==M5PM1_OK &&
        power.gpioSetWakeEnable(M5PM1_GPIO_NUM_2,true)==M5PM1_OK;
    if(manual) { power_hint(); }
    led_off();M5.Display.waitDisplay();M5.Display.sleep();
    power.digitalWrite(M5PM1_GPIO_NUM_0,LOW);power.digitalWrite(M5PM1_GPIO_NUM_3,LOW);power.digitalWrite(M5PM1_GPIO_NUM_4,LOW);power.setLdoEnable(false);
    uint8_t wake=0;power.getWakeSource(&wake,M5PM1_CLEAN_ALL);
    if(armed && wake_pin) {
        ESP_LOGI(TAG,"RTC midnight alarm armed; PMIC power-off");
        power.sysCmd(M5PM1_SYS_CMD_OFF);vTaskDelay(pdMS_TO_TICKS(250));
    }
    // If PMIC cutoff is unavailable (e.g. USB supply), use ESP deep sleep.
    // This fallback is a scheduled RTC-like boot, never an extra manual sync.
    ESP_LOGW(TAG,"Using deep-sleep timer fallback (%lu seconds)",static_cast<unsigned long>(seconds));
    esp_sleep_enable_timer_wakeup((uint64_t(seconds)+1)*1000000ULL);esp_deep_sleep_start();
}
}

extern "C" void app_main() {
    setenv("TZ","UTC0",1);tzset();
    auto cfg=M5.config();cfg.clear_display=false;cfg.internal_spk=false;cfg.internal_mic=false;cfg.internal_imu=false;cfg.output_power=false;
    M5.begin(cfg);led_off();
    power.begin(&M5.In_I2C,M5PM1_DEFAULT_ADDR,M5PM1_I2C_FREQ_100K);power.setI2cConfig(0);
    power.pinMode(M5PM1_GPIO_NUM_0,OUTPUT);power.digitalWrite(M5PM1_GPIO_NUM_0,HIGH);
    // M5Unified enables the TF card rail during board init. This application
    // has no SD dependency; switch that rail off as well as card detection.
    power.pinMode(M5PM1_GPIO_NUM_3,OUTPUT);power.digitalWrite(M5PM1_GPIO_NUM_3,LOW);
    power.pinMode(M5PM1_GPIO_NUM_4,OUTPUT);power.digitalWrite(M5PM1_GPIO_NUM_4,LOW);
    power.setLdoEnable(false);
    uint8_t source=0;power.getWakeSource(&source,M5PM1_CLEAN_NONE);
    auto reason=esp_reset_reason();auto sleep_cause=esp_sleep_get_wakeup_cause();
    tr2e::Boot boot=tr2e::Boot::Recovery;
    if(sleep_cause==ESP_SLEEP_WAKEUP_TIMER || (reason==ESP_RST_POWERON && (source&M5PM1_WAKE_SRC_EXT_WAKE))) boot=tr2e::Boot::Rtc;
    else if(reason==ESP_RST_POWERON || reason==ESP_RST_EXT) boot=tr2e::Boot::Manual;
    const bool manual=boot==tr2e::Boot::Manual;if(manual) power_hint();
    ESP_LOGI(TAG,"Calendar boot kind=%u, wake-source=%u",unsigned(boot),source);
    uint16_t battery_mv=0;
    if(power.readVbat(&battery_mv)==M5PM1_OK && battery_mv>0 && battery_mv<3100) {
        ESP_LOGW(TAG,"Low battery: skip refresh and radio");sleep_until_midnight(false);
    }
    // Never erase NVS automatically: existing credentials and annual locks matter.
    state_ok=nvs_flash_init()==ESP_OK;
    M5.Display.setRotation(3);canvas.setPsram(true);canvas.createSprite(M5.Display.width(),M5.Display.height());canvas.setRotation(1);
    frame=static_cast<uint8_t*>(heap_caps_malloc(30000,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
    if(!frame || !canvas.getBuffer() || !pack.open(pack_start,pack_end-pack_start)) {
        ESP_LOGE(TAG,"Calendar resource/memory validation failed");sleep_until_midnight(manual);
    }
    // First operation is local display, before any network initialization.
    bool displayed=show_today();
    if(!displayed) message("时间或年度计划需要检查","按住 A 键重新开机进行设置");
    if(setup_requested(boot)) configure();
    tr2e::Date day{};m5::rtc_time_t clock;uint32_t today=read_clock(day,clock)?tr2e::ordinal(day):0;
    auto state=load_sync();
    if(state_ok && tr2e::shouldSync(boot,today,state)) {
        CalendarCredentials credentials;calendar_load_credentials(credentials);
        // Commit the 15-day attempt deadline BEFORE powering Wi-Fi, including
        // failures. A crash cannot create a daily retry loop or wear battery.
        tr2e::recordAttempt(state,today,false);
        if(save_sync(state)) {
            int64_t utc=0;bool success=calendar_sync_time(credentials,utc) && set_clock(utc);
            if(success && read_clock(day,clock)) {tr2e::recordAttempt(state,tr2e::ordinal(day),true);save_sync(state);}
            ESP_LOGI(TAG,"Time maintenance %s",success?"succeeded":"not available; RTC retained");
        }
    }
    // Sync can cross midnight/year boundary: render the corrected civil date.
    if(!show_today() && !displayed_day) message("时间或年度计划需要检查","按住 A 键重新开机进行设置");
    sleep_until_midnight(manual);
}
