#include "network.h"
#include <atomic>
#include <cstdio>
#include <cstring>
#include <ctime>
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_random.h"
#include "esp_wifi.h"
#include "esp_wifi_default.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "nvs.h"
#include "cJSON.h"

namespace {
bool net_ready=false,wifi_ready=false;
esp_netif_t* netif=nullptr;
EventGroupHandle_t events=nullptr;
esp_event_handler_instance_t wifi_event=nullptr,ip_event=nullptr;
httpd_handle_t server=nullptr;
std::atomic_bool saved{false};
constexpr EventBits_t CONNECTED=1,FAILED=2;

bool init() {
    if(!net_ready) {
        if(esp_netif_init()!=ESP_OK) return false;
        auto err=esp_event_loop_create_default();
        if(err!=ESP_OK && err!=ESP_ERR_INVALID_STATE) return false;
        net_ready=true;
    }
    wifi_init_config_t cfg=WIFI_INIT_CONFIG_DEFAULT();
    if(esp_wifi_init(&cfg)!=ESP_OK) return false;
    wifi_ready=true;return esp_wifi_set_storage(WIFI_STORAGE_RAM)==ESP_OK;
}
void stop() {
    if(wifi_ready) {esp_wifi_stop();esp_wifi_deinit();wifi_ready=false;}
    if(wifi_event) {esp_event_handler_instance_unregister(WIFI_EVENT,ESP_EVENT_ANY_ID,wifi_event);wifi_event=nullptr;}
    if(ip_event) {esp_event_handler_instance_unregister(IP_EVENT,IP_EVENT_STA_GOT_IP,ip_event);ip_event=nullptr;}
    if(netif) {esp_netif_destroy_default_wifi(netif);netif=nullptr;}
    if(events) {vEventGroupDelete(events);events=nullptr;}
}
void event(void*,esp_event_base_t base,int32_t id,void*) {
    if(base==IP_EVENT && id==IP_EVENT_STA_GOT_IP) xEventGroupSetBits(events,CONNECTED);
    if(base==WIFI_EVENT && id==WIFI_EVENT_STA_DISCONNECTED) xEventGroupSetBits(events,FAILED);
}
bool read(const char* space,const char* ssid_key,const char* pass_key,CalendarCredentials& c) {
    nvs_handle_t h;if(nvs_open(space,NVS_READONLY,&h)!=ESP_OK) return false;
    size_t len=sizeof(c.ssid);bool ok=nvs_get_str(h,ssid_key,c.ssid,&len)==ESP_OK;
    len=sizeof(c.password);auto err=nvs_get_str(h,pass_key,c.password,&len);
    if(err!=ESP_OK && err!=ESP_ERR_NVS_NOT_FOUND) ok=false;
    nvs_close(h);return ok && c.ssid[0];
}
bool save(const CalendarCredentials& c) {
    nvs_handle_t h;if(nvs_open("tr2e",NVS_READWRITE,&h)!=ESP_OK) return false;
    bool ok=nvs_set_str(h,"ssid",c.ssid)==ESP_OK && nvs_set_str(h,"pass",c.password)==ESP_OK && nvs_commit(h)==ESP_OK;
    nvs_close(h);return ok;
}
const char PAGE[]=R"HTML(<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tr2e 网络设置</title><style>body{max-width:420px;margin:50px auto;padding:20px;font:18px system-ui;background:#f5f3ed}input,button{box-sizing:border-box;width:100%;padding:14px;margin:10px 0;font:inherit}small{color:#666}</style><h1>Tr2e</h1><p>连接家中的2.4GHz Wi-Fi。日历内容保存在设备内，联网只用于校时。</p><form id="f"><input id="s" placeholder="Wi-Fi名称" maxlength="32" required><input id="p" type="password" placeholder="Wi-Fi密码" maxlength="64"><button>保存并返回日历</button></form><p id="r"></p><small>设置窗口最多开启3分钟，超时自动关闭。</small><script>document.getElementById('f').onsubmit=async e=>{e.preventDefault();try{let x=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ssid:document.getElementById('s').value,password:document.getElementById('p').value})});document.getElementById('r').textContent=x.ok?'已保存，设备将尝试校时并进入休眠。':'保存失败，请检查输入。'}catch(e){document.getElementById('r').textContent='连接已关闭，请重新打开设置。'}};</script></html>)HTML";
esp_err_t get(httpd_req_t* req) {httpd_resp_set_type(req,"text/html; charset=utf-8");return httpd_resp_send(req,PAGE,HTTPD_RESP_USE_STRLEN);}
esp_err_t post(httpd_req_t* req) {
    if(req->content_len<=0 || req->content_len>512) return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Invalid request");
    char buffer[513];int received=0;
    while(received<req->content_len) {int n=httpd_req_recv(req,buffer+received,req->content_len-received);if(n<=0) return ESP_FAIL;received+=n;}
    buffer[received]=0;cJSON* j=cJSON_Parse(buffer);if(!j) return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Invalid JSON");
    cJSON* s=cJSON_GetObjectItem(j,"ssid");cJSON* p=cJSON_GetObjectItem(j,"password");
    bool valid=cJSON_IsString(s) && cJSON_IsString(p) && strlen(s->valuestring)>0 && strlen(s->valuestring)<=32 && strlen(p->valuestring)<=64;
    CalendarCredentials c;if(valid){snprintf(c.ssid,sizeof(c.ssid),"%s",s->valuestring);snprintf(c.password,sizeof(c.password),"%s",p->valuestring);}
    cJSON_Delete(j);if(!valid) return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Invalid credentials");
    if(!save(c)) return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"Save failed");
    auto result=httpd_resp_sendstr(req,"Saved");saved.store(true);return result;
}
}

bool calendar_load_credentials(CalendarCredentials& c) {
    c={};if(read("tr2e","ssid","pass",c)) return true;
    c={};if(read("papercolor","wifi_ssid","wifi_pass",c)) {save(c);return true;}
    c={};return false;
}
bool calendar_sync_time(const CalendarCredentials& c,int64_t& utc) {
    if(!c.ssid[0]) return false;
    bool ok=false,sntp=false;
    do {
        if(!init()) break;
        netif=esp_netif_create_default_wifi_sta();events=xEventGroupCreate();if(!netif || !events) break;
        if(esp_event_handler_instance_register(WIFI_EVENT,ESP_EVENT_ANY_ID,event,nullptr,&wifi_event)!=ESP_OK ||
           esp_event_handler_instance_register(IP_EVENT,IP_EVENT_STA_GOT_IP,event,nullptr,&ip_event)!=ESP_OK) break;
        wifi_config_t cfg{};memcpy(cfg.sta.ssid,c.ssid,strlen(c.ssid));memcpy(cfg.sta.password,c.password,strlen(c.password));
        cfg.sta.pmf_cfg.capable=true;cfg.sta.pmf_cfg.required=false;
        if(esp_wifi_set_mode(WIFI_MODE_STA)!=ESP_OK || esp_wifi_set_config(WIFI_IF_STA,&cfg)!=ESP_OK || esp_wifi_start()!=ESP_OK || esp_wifi_connect()!=ESP_OK) break;
        auto bits=xEventGroupWaitBits(events,CONNECTED|FAILED,pdFALSE,pdFALSE,pdMS_TO_TICKS(12000));if(!(bits&CONNECTED)) break;
        esp_sntp_config_t config=ESP_NETIF_SNTP_DEFAULT_CONFIG_MULTIPLE(3,ESP_SNTP_SERVER_LIST("ntp.aliyun.com","time.cloudflare.com","pool.ntp.org"));
        if(esp_netif_sntp_init(&config)!=ESP_OK) break;
        sntp=true;
        if(esp_netif_sntp_sync_wait(pdMS_TO_TICKS(18000))!=ESP_OK) break;
        time_t now=time(nullptr);tm t{};if(!gmtime_r(&now,&t) || t.tm_year+1900<2026 || t.tm_year+1900>2099) break;
        utc=now;ok=true;
    }while(false);
    if(sntp) { esp_netif_sntp_deinit(); }
    stop();return ok;
}
bool calendar_setup_start(char* ssid,unsigned ssid_size,char* password,unsigned password_size) {
    saved.store(false);uint8_t mac[6];esp_read_mac(mac,ESP_MAC_WIFI_SOFTAP);
    snprintf(ssid,ssid_size,"Tr2e-%02X%02X",mac[4],mac[5]);snprintf(password,password_size,"%08lX",static_cast<unsigned long>(esp_random()));
    if(!init()) {stop();return false;}
    netif=esp_netif_create_default_wifi_ap();wifi_config_t cfg{};
    snprintf(reinterpret_cast<char*>(cfg.ap.ssid),sizeof(cfg.ap.ssid),"%s",ssid);
    snprintf(reinterpret_cast<char*>(cfg.ap.password),sizeof(cfg.ap.password),"%s",password);
    cfg.ap.authmode=WIFI_AUTH_WPA2_PSK;cfg.ap.max_connection=1;cfg.ap.channel=6;
    if(!netif || esp_wifi_set_mode(WIFI_MODE_AP)!=ESP_OK || esp_wifi_set_config(WIFI_IF_AP,&cfg)!=ESP_OK || esp_wifi_start()!=ESP_OK) {stop();return false;}
    httpd_config_t config=HTTPD_DEFAULT_CONFIG();config.max_uri_handlers=2;config.recv_wait_timeout=3;config.send_wait_timeout=3;
    if(httpd_start(&server,&config)!=ESP_OK) {stop();return false;}
    httpd_uri_t root{};root.uri="/";root.method=HTTP_GET;root.handler=get;httpd_register_uri_handler(server,&root);
    httpd_uri_t save_route{};save_route.uri="/save";save_route.method=HTTP_POST;save_route.handler=post;httpd_register_uri_handler(server,&save_route);
    return true;
}
bool calendar_setup_saved() {return saved.load();}
void calendar_setup_stop() {if(server) {httpd_stop(server);server=nullptr;}stop();}
