#include "network.h"
#include "esp_netif.h"
#include "dns_server.h"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <vector>
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif_sntp.h"
#include "esp_random.h"
#include "esp_wifi.h"
#include "esp_wifi_default.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "nvs.h"
#include "cJSON.h"

namespace {
constexpr const char* TAG="Tr2eNet";
bool net_ready=false,wifi_ready=false;
esp_netif_t* ap_netif=nullptr;
esp_netif_t* sta_netif=nullptr;
EventGroupHandle_t events=nullptr;
esp_event_handler_instance_t wifi_event=nullptr,ip_event=nullptr;
httpd_handle_t server=nullptr;
dns_server_handle_t dns_server=nullptr;
std::atomic<CalendarSetupState> setup_state{CalendarSetupState::Ready};
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
    if(dns_server) {stop_dns_server(dns_server);dns_server=nullptr;}
    if(wifi_ready) {esp_wifi_stop();esp_wifi_deinit();wifi_ready=false;}
    if(wifi_event) {esp_event_handler_instance_unregister(WIFI_EVENT,ESP_EVENT_ANY_ID,wifi_event);wifi_event=nullptr;}
    if(ip_event) {esp_event_handler_instance_unregister(IP_EVENT,IP_EVENT_STA_GOT_IP,ip_event);ip_event=nullptr;}
    if(ap_netif) {esp_netif_destroy_default_wifi(ap_netif);ap_netif=nullptr;}
    if(sta_netif) {esp_netif_destroy_default_wifi(sta_netif);sta_netif=nullptr;}
    if(events) {vEventGroupDelete(events);events=nullptr;}
}
void event(void*,esp_event_base_t base,int32_t id,void*) {
    if(!events) return;
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
bool connect_credentials(const CalendarCredentials& c) {
    if(!events) return false;
    esp_wifi_disconnect();vTaskDelay(pdMS_TO_TICKS(150));xEventGroupClearBits(events,CONNECTED|FAILED);
    wifi_config_t cfg{};
    memcpy(cfg.sta.ssid,c.ssid,strlen(c.ssid));memcpy(cfg.sta.password,c.password,strlen(c.password));
    cfg.sta.scan_method=WIFI_ALL_CHANNEL_SCAN;cfg.sta.sort_method=WIFI_CONNECT_AP_BY_SIGNAL;
    cfg.sta.pmf_cfg.capable=true;cfg.sta.pmf_cfg.required=false;
    if(esp_wifi_set_config(WIFI_IF_STA,&cfg)!=ESP_OK || esp_wifi_connect()!=ESP_OK) return false;
    auto bits=xEventGroupWaitBits(events,CONNECTED|FAILED,pdTRUE,pdFALSE,pdMS_TO_TICKS(15000));
    return bits&CONNECTED;
}

const char PAGE[]=R"HTML(<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tr2e 配网</title><style>
*{box-sizing:border-box}body{max-width:460px;margin:0 auto;padding:28px 18px 44px;font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#20201d;background:#f3f0e8}h1{margin:0 0 4px;font-size:32px}.sub{margin:0 0 22px;color:#68665f}.card{padding:18px;border:1px solid #d8d2c5;border-radius:16px;background:#fff}.row{display:flex;gap:9px}input,button{min-height:48px;border-radius:10px;font:inherit}input{width:100%;padding:11px 13px;border:1px solid #bbb5aa;background:#fff}button{padding:10px 16px;border:0;background:#1f5d49;color:#fff;font-weight:650}.scan{flex:0 0 auto;background:#e5eee9;color:#174c3b}.nets{margin:10px 0 14px;max-height:238px;overflow:auto;border:1px solid #ddd7ca;border-radius:10px}.net{display:flex;justify-content:space-between;width:100%;padding:12px 13px;border:0;border-bottom:1px solid #eee9df;border-radius:0;text-align:left;background:#fff;color:#222;font-weight:500}.net:last-child{border-bottom:0}.net.sel{background:#dcebe4}.meta{color:#777;font-size:13px}.primary{width:100%;margin-top:14px}.status{min-height:48px;margin:15px 2px 0;color:#4d4b45}.ok{color:#157347}.err{color:#b42318}.hint{font-size:13px;color:#777}</style>
<h1>Tr2e 日历</h1><p class="sub">选择家中的 2.4GHz Wi-Fi，输入密码后设备会先验证连接。</p><div class="card"><div class="row"><input id="ssid" maxlength="32" placeholder="选择或输入 Wi-Fi 名称"><button class="scan" id="scan" type="button">重新扫描</button></div><div class="nets" id="nets"><div class="net meta">正在扫描附近网络…</div></div><input id="pass" type="password" maxlength="64" placeholder="Wi-Fi 密码（开放网络可留空）"><button class="primary" id="save" type="button">连接并保存</button><div class="status" id="status"></div><div class="hint">连接验证最多约 15 秒；成功后设备会自动返回日历并校时。</div></div>
<script>
const q=x=>document.getElementById(x),esc=s=>{const d=document.createElement('div');d.textContent=s;return d.innerHTML};
async function scan(){q('scan').disabled=true;q('nets').innerHTML='<div class="net meta">正在扫描附近网络…</div>';try{const r=await fetch('/scan',{cache:'no-store'}),j=await r.json();if(!j.networks.length){q('nets').innerHTML='<div class="net meta">未找到网络，也可以手动输入名称</div>';return}q('nets').innerHTML=j.networks.map((n,i)=>`<button class="net" type="button" data-i="${i}" data-s="${encodeURIComponent(n.ssid)}"><span>${esc(n.ssid)}</span><span class="meta">${n.secure?'🔒 ':''}${n.rssi} dBm</span></button>`).join('');document.querySelectorAll('.net[data-s]').forEach(b=>b.onclick=()=>{document.querySelectorAll('.net').forEach(x=>x.classList.remove('sel'));b.classList.add('sel');q('ssid').value=decodeURIComponent(b.dataset.s);q('pass').focus()})}catch(e){q('nets').innerHTML='<div class="net meta">扫描失败，请点“重新扫描”</div>'}finally{q('scan').disabled=false}}
q('scan').onclick=scan;q('save').onclick=async()=>{const ssid=q('ssid').value.trim();if(!ssid){q('status').className='status err';q('status').textContent='请先选择或输入 Wi-Fi 名称。';return}q('save').disabled=true;q('status').className='status';q('status').textContent='正在连接并验证，请保持此页面打开…';try{const r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ssid,password:q('pass').value})}),j=await r.json();if(!r.ok)throw new Error(j.message||'连接失败');q('status').className='status ok';q('status').textContent='连接成功，配置已保存。设备将自动返回日历。'}catch(e){q('status').className='status err';q('status').textContent=e.message||'连接中断；若设备已退出配网，说明配置已生效。';q('save').disabled=false}};scan();
</script></html>)HTML";

esp_err_t page(httpd_req_t* req) {httpd_resp_set_type(req,"text/html; charset=utf-8");return httpd_resp_send(req,PAGE,HTTPD_RESP_USE_STRLEN);}
esp_err_t scan(httpd_req_t* req) {
    wifi_scan_config_t cfg{};cfg.show_hidden=false;
    if(esp_wifi_scan_start(&cfg,true)!=ESP_OK) return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"Scan failed");
    uint16_t count=0;esp_wifi_scan_get_ap_num(&count);count=std::min<uint16_t>(count,30);
    std::vector<wifi_ap_record_t> records(count);
    if(count && esp_wifi_scan_get_ap_records(&count,records.data())!=ESP_OK)
        return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"Scan failed");
    cJSON* root=cJSON_CreateObject();cJSON* list=cJSON_AddArrayToObject(root,"networks");
    std::vector<const wifi_ap_record_t*> unique;
    for(const auto& record:records) {
        if(!record.ssid[0]) continue;
        bool duplicate=std::any_of(unique.begin(),unique.end(),[&](const auto* other){return strcmp(reinterpret_cast<const char*>(other->ssid),reinterpret_cast<const char*>(record.ssid))==0;});
        if(!duplicate) unique.push_back(&record);
    }
    for(const auto* record:unique) {
        cJSON* item=cJSON_CreateObject();cJSON_AddStringToObject(item,"ssid",reinterpret_cast<const char*>(record->ssid));
        cJSON_AddNumberToObject(item,"rssi",record->rssi);cJSON_AddBoolToObject(item,"secure",record->authmode!=WIFI_AUTH_OPEN);cJSON_AddItemToArray(list,item);
    }
    char* json=cJSON_PrintUnformatted(root);cJSON_Delete(root);
    if(!json) return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"Out of memory");
    httpd_resp_set_type(req,"application/json");auto result=httpd_resp_sendstr(req,json);free(json);return result;
}
esp_err_t post(httpd_req_t* req) {
    if(req->content_len<=0 || req->content_len>512) return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Invalid request");
    char buffer[513];int received=0;
    while(received<req->content_len) {int n=httpd_req_recv(req,buffer+received,req->content_len-received);if(n<=0) return ESP_FAIL;received+=n;}
    buffer[received]=0;cJSON* j=cJSON_Parse(buffer);if(!j) return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Invalid JSON");
    cJSON* s=cJSON_GetObjectItem(j,"ssid");cJSON* p=cJSON_GetObjectItem(j,"password");
    bool valid=cJSON_IsString(s) && cJSON_IsString(p) && strlen(s->valuestring)>0 && strlen(s->valuestring)<=32 && strlen(p->valuestring)<=64;
    CalendarCredentials c;if(valid){snprintf(c.ssid,sizeof(c.ssid),"%s",s->valuestring);snprintf(c.password,sizeof(c.password),"%s",p->valuestring);}
    cJSON_Delete(j);httpd_resp_set_type(req,"application/json; charset=utf-8");
    if(!valid) {httpd_resp_set_status(req,"400 Bad Request");return httpd_resp_sendstr(req,"{\"ok\":false,\"message\":\"Wi-Fi 名称或密码格式不正确\"}");}
    setup_state.store(CalendarSetupState::Connecting);
    if(!connect_credentials(c)) {setup_state.store(CalendarSetupState::Failed);httpd_resp_set_status(req,"503 Service Unavailable");return httpd_resp_sendstr(req,"{\"ok\":false,\"message\":\"连接失败，请检查密码、信号或是否为 2.4GHz 网络\"}");}
    if(!save(c)) {setup_state.store(CalendarSetupState::Failed);httpd_resp_set_status(req,"500 Internal Server Error");return httpd_resp_sendstr(req,"{\"ok\":false,\"message\":\"保存失败，请重试\"}");}
    auto result=httpd_resp_sendstr(req,"{\"ok\":true}");setup_state.store(CalendarSetupState::Saved);return result;
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
        sta_netif=esp_netif_create_default_wifi_sta();events=xEventGroupCreate();if(!sta_netif || !events) break;
        if(esp_event_handler_instance_register(WIFI_EVENT,ESP_EVENT_ANY_ID,event,nullptr,&wifi_event)!=ESP_OK || esp_event_handler_instance_register(IP_EVENT,IP_EVENT_STA_GOT_IP,event,nullptr,&ip_event)!=ESP_OK) break;
        wifi_config_t cfg{};memcpy(cfg.sta.ssid,c.ssid,strlen(c.ssid));memcpy(cfg.sta.password,c.password,strlen(c.password));cfg.sta.pmf_cfg.capable=true;cfg.sta.pmf_cfg.required=false;
        if(esp_wifi_set_mode(WIFI_MODE_STA)!=ESP_OK || esp_wifi_set_config(WIFI_IF_STA,&cfg)!=ESP_OK || esp_wifi_start()!=ESP_OK || esp_wifi_connect()!=ESP_OK) break;
        auto bits=xEventGroupWaitBits(events,CONNECTED|FAILED,pdFALSE,pdFALSE,pdMS_TO_TICKS(12000));if(!(bits&CONNECTED)) break;
        esp_sntp_config_t config=ESP_NETIF_SNTP_DEFAULT_CONFIG_MULTIPLE(3,ESP_SNTP_SERVER_LIST("ntp.aliyun.com","time.cloudflare.com","pool.ntp.org"));
        if(esp_netif_sntp_init(&config)!=ESP_OK) break;
        sntp=true;
        if(esp_netif_sntp_sync_wait(pdMS_TO_TICKS(18000))!=ESP_OK) break;
        time_t now=time(nullptr);tm t{};if(!gmtime_r(&now,&t) || t.tm_year+1900<2026 || t.tm_year+1900>2099) break;
        utc=now;ok=true;
    }while(false);
    if(sntp) esp_netif_sntp_deinit();
    stop();return ok;
}
bool calendar_setup_start(char* ssid,unsigned ssid_size,char* password,unsigned password_size) {
    setup_state.store(CalendarSetupState::Ready);uint8_t mac[6];esp_read_mac(mac,ESP_MAC_WIFI_SOFTAP);
    snprintf(ssid,ssid_size,"Tr2e-%02X%02X",mac[4],mac[5]);snprintf(password,password_size,"%08lX",static_cast<unsigned long>(esp_random()));
    if(!init()) {stop();return false;}
    ap_netif=esp_netif_create_default_wifi_ap();sta_netif=esp_netif_create_default_wifi_sta();events=xEventGroupCreate();if(!ap_netif || !sta_netif || !events) {stop();return false;}
    if(esp_event_handler_instance_register(WIFI_EVENT,ESP_EVENT_ANY_ID,event,nullptr,&wifi_event)!=ESP_OK || esp_event_handler_instance_register(IP_EVENT,IP_EVENT_STA_GOT_IP,event,nullptr,&ip_event)!=ESP_OK) {stop();return false;}
    wifi_config_t cfg{};snprintf(reinterpret_cast<char*>(cfg.ap.ssid),sizeof(cfg.ap.ssid),"%s",ssid);cfg.ap.ssid_len=strlen(reinterpret_cast<char*>(cfg.ap.ssid));
    snprintf(reinterpret_cast<char*>(cfg.ap.password),sizeof(cfg.ap.password),"%s",password);cfg.ap.authmode=WIFI_AUTH_WPA2_PSK;cfg.ap.max_connection=2;cfg.ap.channel=6;
    if(esp_wifi_set_mode(WIFI_MODE_APSTA)!=ESP_OK || esp_wifi_set_config(WIFI_IF_AP,&cfg)!=ESP_OK || esp_wifi_start()!=ESP_OK) {stop();return false;}
    httpd_config_t config=HTTPD_DEFAULT_CONFIG();config.max_uri_handlers=4;config.recv_wait_timeout=18;config.send_wait_timeout=5;config.uri_match_fn=httpd_uri_match_wildcard;
    if(httpd_start(&server,&config)!=ESP_OK) {stop();return false;}
    httpd_uri_t root{};root.uri="/";root.method=HTTP_GET;root.handler=page;httpd_register_uri_handler(server,&root);
    httpd_uri_t scan_route{};scan_route.uri="/scan";scan_route.method=HTTP_GET;scan_route.handler=scan;httpd_register_uri_handler(server,&scan_route);
    httpd_uri_t save_route{};save_route.uri="/save";save_route.method=HTTP_POST;save_route.handler=post;httpd_register_uri_handler(server,&save_route);
    httpd_uri_t captive{};captive.uri="/*";captive.method=HTTP_GET;captive.handler=page;httpd_register_uri_handler(server,&captive);
    dns_server_config_t dns_config{};dns_config.num_of_entries=1;
    dns_config.item[0].name="*";dns_config.item[0].if_key="WIFI_AP_DEF";
    dns_server=start_dns_server(&dns_config);
    if(!dns_server) {httpd_stop(server);server=nullptr;stop();return false;}
    ESP_LOGI(TAG,"Setup AP started: ssid=%s channel=%u",ssid,unsigned(cfg.ap.channel));return true;
}
bool calendar_setup_saved() {return setup_state.load()==CalendarSetupState::Saved;}
CalendarSetupState calendar_setup_state() {return setup_state.load();}
void calendar_setup_stop() {if(server) {httpd_stop(server);server=nullptr;}stop();}
